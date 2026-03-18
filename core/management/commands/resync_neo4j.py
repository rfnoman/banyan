"""
Full re-sync from PostgreSQL to Neo4j.
Clears all Neo4j data and re-creates from PostgreSQL — use for disaster recovery.
"""
from django.core.management.base import BaseCommand

from core.graph.driver import get_driver
from core.models import Business, Lead, Person, Product


class Command(BaseCommand):
    help = "Full re-sync: clear Neo4j and rebuild from PostgreSQL"

    def add_arguments(self, parser):
        parser.add_argument(
            "--confirm", action="store_true",
            help="Required to actually run (destructive operation)",
        )

    def handle(self, *args, **options):
        if not options["confirm"]:
            self.stdout.write(self.style.WARNING(
                "This will CLEAR all Neo4j data and re-sync from PostgreSQL.\n"
                "Run with --confirm to proceed."
            ))
            return

        driver = get_driver()

        self.stdout.write("Clearing Neo4j...")
        with driver.session() as s:
            s.run("MATCH (n) DETACH DELETE n")

        self.stdout.write("Syncing businesses...")
        for biz in Business.objects.all():
            with driver.session() as s:
                s.run(
                    "CREATE (b:Business {id: $id, name: $name, industry: $industry, size: $size, website: $website})",
                    id=biz.id, name=biz.name, industry=biz.industry or "",
                    size=biz.size or "", website=biz.website or "",
                )
        self.stdout.write(f"  {Business.objects.count()} businesses")

        self.stdout.write("Syncing products...")
        for prod in Product.objects.all():
            with driver.session() as s:
                s.run(
                    "CREATE (p:Product {id: $id, name: $name, url: $url, description: $description})",
                    id=prod.id, name=prod.name, url=prod.url or "",
                    description=prod.description or "",
                )
        self.stdout.write(f"  {Product.objects.count()} products")

        self.stdout.write("Syncing persons...")
        for person in Person.objects.select_related("company").all():
            with driver.session() as s:
                s.run(
                    """
                    CREATE (p:Person {
                        id: $id, name: $name, email: $email, title: $title,
                        score: $score, source: $source,
                        linkedin_url: $linkedin_url, location: $location,
                        ai_tag_status: $ai_tag_status, ai_persona: $ai_persona
                    })
                    """,
                    id=person.id, name=person.name, email=person.email,
                    title=person.title or "", score=person.score,
                    source=person.source or "", linkedin_url=person.linkedin_url or "",
                    location=person.location or "", ai_tag_status=person.ai_tag_status or "",
                    ai_persona=person.ai_persona or "",
                )
                if person.company_id:
                    s.run(
                        """
                        MATCH (p:Person {id: $pid})
                        MATCH (b:Business {id: $bid})
                        CREATE (p)-[:WORKS_AT]->(b)
                        """,
                        pid=person.id, bid=person.company_id,
                    )
        self.stdout.write(f"  {Person.objects.count()} persons")

        self.stdout.write("Syncing leads...")
        for lead in Lead.objects.all():
            with driver.session() as s:
                s.run(
                    """
                    MATCH (p:Person {id: $pid})
                    MATCH (prod:Product {id: $prod_id})
                    CREATE (p)-[:IS_LEAD_FOR {stage: $stage, score: $score}]->(prod)
                    """,
                    pid=lead.person_id, prod_id=lead.product_id,
                    stage=lead.stage, score=lead.score,
                )
        self.stdout.write(f"  {Lead.objects.count()} leads")

        # Re-apply constraints
        from core.graph.schema import apply_schema
        apply_schema()

        self.stdout.write(self.style.SUCCESS("\nRe-sync complete."))
