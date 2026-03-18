from django.core.management.base import BaseCommand, CommandParser

from integrations.external.events import on_contact_created, on_contact_updated

FAKE_CONTACTS = [
    {
        "name": "Liam Chen",
        "email": "liam.chen@greenleaf.io",
        "title": "VP of Sustainability",
        "company": "GreenLeaf Technologies",
        "industry": "CleanTech",
        "company_size": "200",
        "website": "https://greenleaf.io",
        "location": "San Francisco, CA",
        "is_paid": True,
        "product": "ProductA",
        "notes": "Interested in carbon tracking module",
    },
    {
        "name": "Amara Osei",
        "email": "amara@solarflux.co",
        "title": "CTO",
        "company": "SolarFlux Energy",
        "industry": "Renewable Energy",
        "company_size": "85",
        "is_paid": True,
        "product": "ProductB",
        "notes": "Evaluating API integration for energy dashboards",
    },
    {
        "name": "Priya Sharma",
        "email": "priya@ecochain.com",
        "title": "Head of Operations",
        "company": "EcoChain Supply",
        "industry": "Supply Chain",
        "company_size": "150",
        "is_paid": False,
        "product": "ProductA",
        "notes": "Wants ESG reporting features",
    },
    {
        "name": "Marcus Rivera",
        "email": "marcus@terranova.dev",
        "title": "Founder & CEO",
        "company": "TerraNova Dev",
        "industry": "AgriTech",
        "company_size": "30",
        "is_paid": False,
        "product": "ProductC",
        "notes": "Early stage, exploring precision agriculture tools",
    },
    {
        "name": "Elena Petrova",
        "email": "elena.p@blueocean.eu",
        "title": "Director of Partnerships",
        "company": "BlueOcean Analytics",
        "industry": "Environmental Analytics",
        "company_size": "300",
        "website": "https://blueocean.eu",
        "is_paid": True,
        "product": "ProductB",
        "notes": "Looking to integrate water quality data feeds",
    },
]


class Command(BaseCommand):
    help = "Simulate external app contact events (specify --source for app name)"

    def add_arguments(self, parser: CommandParser):
        parser.add_argument(
            "--source",
            type=str,
            default="greenforest",
            help="Source app name (e.g., greenforest, otherapp)",
        )

    def handle(self, *args, **options):
        source = options["source"]
        self.stdout.write(f"Simulating contact events from '{source}'...\n")

        for i, contact in enumerate(FAKE_CONTACTS):
            try:
                if i % 2 == 0:
                    on_contact_created(contact, source)
                    self.stdout.write(
                        self.style.SUCCESS(f"  [created] {contact['name']} ({contact['email']})")
                    )
                else:
                    on_contact_updated(contact, source)
                    self.stdout.write(
                        self.style.SUCCESS(f"  [updated] {contact['name']} ({contact['email']})")
                    )
            except Exception as exc:
                self.stdout.write(
                    self.style.ERROR(f"  [FAILED] {contact['name']}: {exc}")
                )

        self.stdout.write(self.style.SUCCESS(f"\nDone. Events published as '{source}'."))
