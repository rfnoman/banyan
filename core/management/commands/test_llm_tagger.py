import json
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Run LLM tagger on a person and print result (bypasses RabbitMQ)"

    def add_arguments(self, parser):
        parser.add_argument("--person-id", dest="person_id", required=True, help="Person UUID in Neo4j")

    def handle(self, *args, **options):
        person_id = options["person_id"]
        self.stdout.write(self.style.MIGRATE_HEADING(f"\n=== LLM Tagger: {person_id} ===\n"))

        try:
            from core.llm.tagger import LeadTagger
            tagger = LeadTagger()
            result = tagger.tag_person(
                person_id,
                raw_context="",
                trigger="test_command",
                source_app="manage.py",
            )
            self.stdout.write(self.style.SUCCESS("\nAITagResult:"))
            self.stdout.write(json.dumps(result.model_dump(), indent=2))
        except Exception as exc:
            raise CommandError(f"Tagger failed: {exc}") from exc
