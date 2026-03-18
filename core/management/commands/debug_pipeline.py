"""
Management command: python manage.py debug_pipeline

Runs CRM pipeline flows synchronously — no RabbitMQ, no Celery worker needed.
All Celery tasks are called via .apply() so they execute inline in this process.

Usage:
    # Fire a fake lead through the full ingestion pipeline
    python manage.py debug_pipeline --event lead

    # Re-score a specific person (must exist in Neo4j)
    python manage.py debug_pipeline --event score --person-id <uuid>

    # Run LLM tagger on a person and print AITagResult
    python manage.py debug_pipeline --event llm --person-id <uuid>

    # Log a fake action for a person
    python manage.py debug_pipeline --event action --person-id <uuid>
"""

import json
import uuid
from datetime import datetime, timezone

from django.core.management.base import BaseCommand, CommandError


FAKE_LEAD_EVENT = {
    "event_type": "lead.created",
    "source_app": "debug_tool",
    "source_product": "ProductA",
    "person": {
        "name": "Alex Debug",
        "email": f"debug-{uuid.uuid4().hex[:6]}@example.com",
        "title": "VP of Engineering",
        "company": "Debug Corp",
        "linkedin_url": "https://linkedin.com/in/alexdebug",
        "location": "San Francisco, CA",
    },
    "company": {
        "name": "Debug Corp",
        "industry": "SaaS",
        "size": "150",
        "website": "https://debugcorp.com",
    },
    "trigger": "contact_updated",
    "score_hints": {"is_paid": True},
    "raw_context": (
        "Alex Debug is a VP of Engineering at Debug Corp, a 150-person SaaS company. "
        "They updated their profile indicating active engagement. "
        "The company recently raised Series B and is actively hiring engineers."
    ),
    "timestamp": datetime.now(timezone.utc).isoformat(),
}

FAKE_ACTION_EVENT = {
    "event_type": "action.logged",
    "action_type": "email_sent",
    "note": "Sent intro email — debug",
    "channel": "email",
    "source_app": "debug_tool",
}


class Command(BaseCommand):
    help = "Debug CRM pipeline flows synchronously (no queue/worker needed)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--event",
            choices=["lead", "action", "score", "llm"],
            required=True,
            help="Which flow to trigger: lead | action | score | llm",
        )
        parser.add_argument(
            "--person-id",
            dest="person_id",
            default=None,
            help="Target person UUID (required for action, score, llm events)",
        )

    def handle(self, *args, **options):
        event = options["event"]
        person_id = options["person_id"]

        self.stdout.write(self.style.MIGRATE_HEADING(f"\n=== debug_pipeline --event {event} ===\n"))

        if event == "lead":
            self._run_lead()
        elif event == "action":
            self._require_person_id(person_id, event)
            self._run_action(person_id)
        elif event == "score":
            self._require_person_id(person_id, event)
            self._run_score(person_id)
        elif event == "llm":
            self._require_person_id(person_id, event)
            self._run_llm(person_id)

    # ──────────────────────────────────────────────────────────────────────────

    def _require_person_id(self, person_id, event):
        if not person_id:
            raise CommandError(f"--person-id is required for --event {event}")

    def _run_lead(self):
        from core.tasks.lead_tasks import process_incoming_lead  # noqa: PLC0415

        self.stdout.write("Firing fake LeadCreatedEvent through pipeline...")
        self.stdout.write(self.style.WARNING("Person: " + FAKE_LEAD_EVENT["person"]["name"]))
        self.stdout.write(self.style.WARNING("Email:  " + FAKE_LEAD_EVENT["person"]["email"]))

        result = process_incoming_lead.apply(args=[FAKE_LEAD_EVENT])

        if result.successful():
            self.stdout.write(self.style.SUCCESS("\nPipeline result:"))
            self.stdout.write(json.dumps(result.result, indent=2, default=str))
        else:
            self.stdout.write(self.style.ERROR(f"\nTask failed: {result.result}"))

    def _run_action(self, person_id):
        from core.tasks.action_tasks import process_action_logged  # noqa: PLC0415

        event = {**FAKE_ACTION_EVENT, "person_id": person_id}
        self.stdout.write(f"Logging fake action for person {person_id}...")

        result = process_action_logged.apply(args=[event])

        if result.successful():
            self.stdout.write(self.style.SUCCESS("\nAction logged:"))
            self.stdout.write(json.dumps(result.result, indent=2, default=str))
        else:
            self.stdout.write(self.style.ERROR(f"\nTask failed: {result.result}"))

    def _run_score(self, person_id):
        from core.tasks.scoring_tasks import recalculate_lead_score  # noqa: PLC0415

        self.stdout.write(f"Recalculating score for person {person_id}...")

        result = recalculate_lead_score.apply(args=[person_id])

        if result.successful():
            self.stdout.write(self.style.SUCCESS(f"\nNew score: {result.result}"))
        else:
            self.stdout.write(self.style.ERROR(f"\nTask failed: {result.result}"))

    def _run_llm(self, person_id):
        from core.llm.tasks import tag_lead_with_llm  # noqa: PLC0415

        self.stdout.write(f"Running LLM tagger for person {person_id}...")
        self.stdout.write(self.style.WARNING("(Requires ANTHROPIC_API_KEY and person in Neo4j)\n"))

        result = tag_lead_with_llm.apply(kwargs={
            "person_id": person_id,
            "trigger": "debug_tool",
            "source_app": "debug_pipeline",
        })

        if result.successful():
            self.stdout.write(self.style.SUCCESS("\nAITagResult:"))
            self.stdout.write(json.dumps(result.result, indent=2, default=str))
        else:
            self.stdout.write(self.style.ERROR(f"\nTask failed: {result.result}"))
