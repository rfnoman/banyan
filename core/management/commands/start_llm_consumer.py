from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Start the RabbitMQ LLM consumer (crm.leads.llm_tagging + crm.ai.tag_requested)"

    def handle(self, *args, **options):
        from core.llm.consumer import LLMConsumer
        self.stdout.write(self.style.SUCCESS("Starting LLM consumer..."))
        LLMConsumer().run()
