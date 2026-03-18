from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Start the RabbitMQ lead consumer (crm.leads.ingest)"

    def handle(self, *args, **options):
        from core.consumers.lead_consumer import LeadConsumer
        self.stdout.write(self.style.SUCCESS("Starting lead consumer..."))
        LeadConsumer().run()
