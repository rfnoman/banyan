import uuid
from django.core.management.base import BaseCommand

FAKE_CONTACTS = [
    {"name": "Sarah Chen", "email": f"sarah.chen.{uuid.uuid4().hex[:4]}@techcorp.com", "title": "VP of Engineering",
     "company": "TechCorp", "industry": "SaaS", "company_size": "150", "is_paid": True,
     "notes": "Active user, recently upgraded plan", "product": "ProductA"},
    {"name": "James Okafor", "email": f"james.okafor.{uuid.uuid4().hex[:4]}@finserv.io", "title": "CTO",
     "company": "FinServ IO", "industry": "FinTech", "company_size": "80", "is_paid": True,
     "notes": "Evaluating competitor solutions", "product": "ProductB"},
    {"name": "Maria Santos", "email": f"maria.santos.{uuid.uuid4().hex[:4]}@growthco.com", "title": "Head of Operations",
     "company": "GrowthCo", "industry": "E-commerce", "company_size": "45", "is_paid": False,
     "notes": "Free tier user asking about enterprise features", "product": "ProductA"},
    {"name": "David Kim", "email": f"david.kim.{uuid.uuid4().hex[:4]}@startup.ai", "title": "Founder & CEO",
     "company": "Startup AI", "industry": "AI/ML", "company_size": "12", "is_paid": False,
     "linkedin_url": "https://linkedin.com/in/davidkim", "notes": "Y Combinator W24", "product": "ProductC"},
    {"name": "Rachel Green", "email": f"rachel.green.{uuid.uuid4().hex[:4]}@enterprise.co", "title": "Director of Finance",
     "company": "Enterprise Co", "industry": "Enterprise Software", "company_size": "500", "is_paid": True,
     "notes": "Renewal coming up, interested in analytics add-on", "product": "ProductB"},
]

FAKE_BUSINESSES = [
    {"name": "CloudBase Inc", "industry": "Cloud Infrastructure", "plan": "enterprise", "size": "200",
     "contact_name": "Tom Bradley", "contact_email": f"tom.{uuid.uuid4().hex[:4]}@cloudbase.io", "product": "ProductA"},
    {"name": "DataFlow Labs", "industry": "Data Analytics", "plan": "pro", "size": "35",
     "contact_name": "Amy Wu", "contact_email": f"amy.{uuid.uuid4().hex[:4]}@dataflow.io", "product": "ProductB"},
    {"name": "SecureStack", "industry": "Cybersecurity", "plan": "free", "size": "8",
     "contact_name": "Mike Torres", "contact_email": f"mike.{uuid.uuid4().hex[:4]}@securestack.dev", "product": "ProductC"},
    {"name": "RetailEdge", "industry": "Retail Tech", "plan": "starter", "size": "60",
     "contact_name": "Lisa Park", "contact_email": f"lisa.{uuid.uuid4().hex[:4]}@retailedge.com", "product": "ProductA"},
    {"name": "MedTech Solutions", "industry": "Healthcare", "plan": "enterprise", "size": "300",
     "contact_name": "Dr. Amir Patel", "contact_email": f"amir.{uuid.uuid4().hex[:4]}@medtech.co", "product": "ProductB"},
]


class Command(BaseCommand):
    help = "Send 5 fake Bookkeeper events of each type (contact_updated, business_signup)"

    def handle(self, *args, **options):
        from integrations.bookkeeper.events import on_contact_updated, on_business_signup

        self.stdout.write(self.style.MIGRATE_HEADING("\n=== Simulating Bookkeeper events ===\n"))

        self.stdout.write("Sending contact_updated events...")
        for contact in FAKE_CONTACTS:
            try:
                on_contact_updated(contact)
                self.stdout.write(self.style.SUCCESS(f"  ✓ contact_updated: {contact['name']} <{contact['email']}>"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  ✗ {contact['name']}: {e}"))

        self.stdout.write("\nSending business_signup events...")
        for business in FAKE_BUSINESSES:
            try:
                on_business_signup(business)
                self.stdout.write(self.style.SUCCESS(f"  ✓ business_signup: {business['name']}"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  ✗ {business['name']}: {e}"))

        self.stdout.write(self.style.SUCCESS("\nDone. Check RabbitMQ crm.leads.ingest queue for messages."))
