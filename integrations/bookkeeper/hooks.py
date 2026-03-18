"""
Django signal receivers for Bookkeeper integration.

Connect these signals in your AppConfig.ready() if using Django signals,
or call the event handlers directly from your Bookkeeper app code.
"""
from django.dispatch import Signal, receiver

contact_updated = Signal()
business_signed_up = Signal()
invoice_sent = Signal()


@receiver(contact_updated)
def handle_contact_updated(sender, contact: dict, **kwargs):
    from integrations.bookkeeper.events import on_contact_updated
    on_contact_updated(contact)


@receiver(business_signed_up)
def handle_business_signup(sender, business: dict, **kwargs):
    from integrations.bookkeeper.events import on_business_signup
    on_business_signup(business)


@receiver(invoice_sent)
def handle_invoice_sent(sender, invoice: dict, **kwargs):
    from integrations.bookkeeper.events import on_invoice_sent
    on_invoice_sent(invoice)
