"""
Migrate all CRM data from Neo4j to PostgreSQL.
Idempotent — safe to run multiple times (uses update_or_create).
"""
import json

from django.core.management.base import BaseCommand
from django.db import transaction

from core.graph.driver import get_driver
from core.models import (
    Action,
    Business,
    Lead,
    Person,
    Product,
    ReferralSource,
    Source,
)


class Command(BaseCommand):
    help = "Migrate CRM data from Neo4j to PostgreSQL"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Count entities without writing")
        parser.add_argument("--verify", action="store_true", help="Compare counts after migration")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        verify = options["verify"]
        driver = get_driver()

        if dry_run:
            self._dry_run(driver)
            return

        self._migrate_businesses(driver)
        self._migrate_products(driver)
        self._migrate_sources(driver)
        self._migrate_persons(driver)
        self._migrate_leads(driver)
        self._migrate_actions(driver)
        self._migrate_referral_sources(driver)

        self.stdout.write(self.style.SUCCESS("\nMigration complete."))

        if verify:
            self._verify(driver)

    def _dry_run(self, driver):
        with driver.session() as s:
            for label in ["Business", "Product", "Source", "Person", "Action"]:
                r = s.run(f"MATCH (n:{label}) RETURN count(n) AS c").single()
                self.stdout.write(f"  {label}: {r['c']}")
            r = s.run(
                "MATCH ()-[r:IS_LEAD_FOR]->() RETURN count(r) AS c"
            ).single()
            self.stdout.write(f"  Leads (IS_LEAD_FOR): {r['c']}")
            r = s.run(
                "MATCH ()-[r:REFERRED_FROM]->() RETURN count(r) AS c"
            ).single()
            self.stdout.write(f"  ReferralSources (REFERRED_FROM): {r['c']}")

    @transaction.atomic
    def _migrate_businesses(self, driver):
        count = 0
        with driver.session() as s:
            for record in s.run("MATCH (b:Business) RETURN b"):
                b = dict(record["b"])
                Business.objects.update_or_create(
                    name=b.get("name", ""),
                    defaults={
                        "id": b.get("id", ""),
                        "industry": b.get("industry"),
                        "size": b.get("size"),
                        "website": b.get("website"),
                        "location": b.get("location"),
                    },
                )
                count += 1
        self.stdout.write(self.style.SUCCESS(f"  Businesses: {count}"))

    @transaction.atomic
    def _migrate_products(self, driver):
        count = 0
        with driver.session() as s:
            for record in s.run("MATCH (p:Product) RETURN p"):
                p = dict(record["p"])
                Product.objects.update_or_create(
                    name=p.get("name", ""),
                    defaults={
                        "id": p.get("id", ""),
                        "url": p.get("url"),
                        "description": p.get("description"),
                    },
                )
                count += 1
        self.stdout.write(self.style.SUCCESS(f"  Products: {count}"))

    @transaction.atomic
    def _migrate_sources(self, driver):
        count = 0
        with driver.session() as s:
            for record in s.run("MATCH (s:Source) RETURN s"):
                src = dict(record["s"])
                Source.objects.update_or_create(
                    name=src.get("name", ""),
                    defaults={"id": src.get("id", "")},
                )
                count += 1
        self.stdout.write(self.style.SUCCESS(f"  Sources: {count}"))

    @transaction.atomic
    def _migrate_persons(self, driver):
        count = 0
        with driver.session() as s:
            results = s.run(
                """
                MATCH (p:Person)
                OPTIONAL MATCH (p)-[:WORKS_AT]->(b:Business)
                RETURN p, b.name AS company_name
                """
            )
            for record in results:
                p = dict(record["p"])
                company_name = record["company_name"]

                # Resolve company FK
                company_id = None
                if company_name:
                    try:
                        company_id = Business.objects.get(name=company_name).id
                    except Business.DoesNotExist:
                        pass

                # Parse ai_tags
                ai_tags = p.get("ai_tags", [])
                if isinstance(ai_tags, str):
                    try:
                        ai_tags = json.loads(ai_tags)
                    except Exception:
                        ai_tags = []

                Person.objects.update_or_create(
                    email=p.get("email", ""),
                    defaults={
                        "id": p.get("id", ""),
                        "name": p.get("name", ""),
                        "title": p.get("title"),
                        "linkedin_url": p.get("linkedin_url"),
                        "location": p.get("location"),
                        "source": p.get("source"),
                        "score": float(p.get("score", 0)),
                        "company_id": company_id,
                        "ai_tags": ai_tags,
                        "ai_persona": p.get("ai_persona"),
                        "ai_product_fit": p.get("ai_product_fit"),
                        "ai_urgency": p.get("ai_urgency"),
                        "ai_reasoning": p.get("ai_reasoning"),
                        "ai_tagged_at": p.get("ai_tagged_at"),
                        "ai_tag_status": p.get("ai_tag_status"),
                        "ai_suggested_stage": p.get("ai_suggested_stage"),
                        "ai_confidence": float(p.get("ai_confidence", 0)),
                        "ai_model_used": p.get("ai_model_used"),
                        "ai_tokens_used": int(p.get("ai_tokens_used", 0)),
                    },
                )
                count += 1
        self.stdout.write(self.style.SUCCESS(f"  Persons: {count}"))

    @transaction.atomic
    def _migrate_leads(self, driver):
        count = 0
        with driver.session() as s:
            results = s.run(
                """
                MATCH (p:Person)-[r:IS_LEAD_FOR]->(prod:Product)
                RETURN p.id AS person_id, prod.name AS product_name,
                       r.stage AS stage, r.score AS score
                """
            )
            for record in results:
                try:
                    person = Person.objects.get(id=record["person_id"])
                except Person.DoesNotExist:
                    continue
                product, _ = Product.objects.get_or_create(
                    name=record["product_name"],
                )
                Lead.objects.update_or_create(
                    person=person,
                    product=product,
                    defaults={
                        "stage": record["stage"] or "New Lead",
                        "score": float(record["score"] or 0),
                    },
                )
                count += 1
        self.stdout.write(self.style.SUCCESS(f"  Leads: {count}"))

    @transaction.atomic
    def _migrate_actions(self, driver):
        count = 0
        with driver.session() as s:
            results = s.run(
                """
                MATCH (p:Person)-[:HAS_ACTION]->(a:Action)
                RETURN p.id AS person_id, a
                """
            )
            for record in results:
                a = dict(record["a"])
                try:
                    person = Person.objects.get(id=record["person_id"])
                except Person.DoesNotExist:
                    continue
                Action.objects.update_or_create(
                    id=a.get("id", ""),
                    defaults={
                        "person": person,
                        "type": a.get("type", ""),
                        "note": a.get("note", ""),
                        "channel": a.get("channel", ""),
                    },
                )
                count += 1
        self.stdout.write(self.style.SUCCESS(f"  Actions: {count}"))

    @transaction.atomic
    def _migrate_referral_sources(self, driver):
        count = 0
        with driver.session() as s:
            results = s.run(
                """
                MATCH (p:Person)-[r:REFERRED_FROM]->(src:Source)
                RETURN p.id AS person_id, src.name AS source_name,
                       r.trigger AS trigger, r.event_count AS event_count
                """
            )
            for record in results:
                try:
                    person = Person.objects.get(id=record["person_id"])
                except Person.DoesNotExist:
                    continue
                source, _ = Source.objects.get_or_create(name=record["source_name"])
                ReferralSource.objects.update_or_create(
                    person=person,
                    source=source,
                    defaults={
                        "trigger": record["trigger"] or "",
                        "event_count": int(record["event_count"] or 1),
                    },
                )
                count += 1
        self.stdout.write(self.style.SUCCESS(f"  ReferralSources: {count}"))

    def _verify(self, driver):
        self.stdout.write("\nVerification:")
        checks = [
            ("Person", Person.objects.count()),
            ("Business", Business.objects.count()),
            ("Product", Product.objects.count()),
            ("Source", Source.objects.count()),
            ("Lead", Lead.objects.count()),
            ("Action", Action.objects.count()),
            ("ReferralSource", ReferralSource.objects.count()),
        ]
        neo4j_queries = {
            "Person": "MATCH (n:Person) RETURN count(n) AS c",
            "Business": "MATCH (n:Business) RETURN count(n) AS c",
            "Product": "MATCH (n:Product) RETURN count(n) AS c",
            "Source": "MATCH (n:Source) RETURN count(n) AS c",
            "Lead": "MATCH ()-[r:IS_LEAD_FOR]->() RETURN count(r) AS c",
            "Action": "MATCH (n:Action) RETURN count(n) AS c",
            "ReferralSource": "MATCH ()-[r:REFERRED_FROM]->() RETURN count(r) AS c",
        }
        with driver.session() as s:
            for label, pg_count in checks:
                neo4j_count = s.run(neo4j_queries[label]).single()["c"]
                match = "OK" if pg_count == neo4j_count else "MISMATCH"
                style = self.style.SUCCESS if match == "OK" else self.style.ERROR
                self.stdout.write(style(
                    f"  {label}: Neo4j={neo4j_count} PostgreSQL={pg_count} [{match}]"
                ))
