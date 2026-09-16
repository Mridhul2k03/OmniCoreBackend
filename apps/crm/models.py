import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _
from apps.core.models import TenantOwnedModel


class CustomerType(models.TextChoices):
    CORPORATE = 'CORPORATE', _('Corporate Enterprise')
    INDIVIDUAL = 'INDIVIDUAL', _('Individual Shipper')
    GOVERNMENT = 'GOVERNMENT', _('Government / Public Sector')
    BROKER = 'BROKER', _('Freight Broker / 3PL')


class LeadStatus(models.TextChoices):
    NEW = 'NEW', _('New Lead')
    CONTACTED = 'CONTACTED', _('Contacted')
    QUALIFIED = 'QUALIFIED', _('Qualified')
    PROPOSAL_SENT = 'PROPOSAL_SENT', _('Proposal Sent')
    NEGOTIATION = 'NEGOTIATION', _('Negotiation')
    WON = 'WON', _('Converted / Won')
    LOST = 'LOST', _('Lost')


class QuotationStatus(models.TextChoices):
    DRAFT = 'DRAFT', _('Draft')
    SENT = 'SENT', _('Sent to Client')
    ACCEPTED = 'ACCEPTED', _('Accepted')
    REJECTED = 'REJECTED', _('Rejected')
    EXPIRED = 'EXPIRED', _('Expired')


class Customer(TenantOwnedModel):
    """
    Client organization or individual commissioning freight & transport services.
    """
    company_name = models.CharField(max_length=255, db_index=True)
    contact_person = models.CharField(max_length=150, blank=True)
    email = models.EmailField(blank=True, db_index=True)
    phone = models.CharField(max_length=30, blank=True, db_index=True)
    address = models.TextField(blank=True)
    tax_id = models.CharField(max_length=100, blank=True, help_text="GST / VAT / EIN")
    customer_type = models.CharField(max_length=30, choices=CustomerType.choices, default=CustomerType.CORPORATE)
    credit_limit = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    payment_terms_days = models.PositiveIntegerField(default=30)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=['tenant', 'company_name']),
            models.Index(fields=['tenant', 'is_active']),
        ]

    def __str__(self):
        return self.company_name


class Lead(TenantOwnedModel):
    """
    Sales prospect prior to becoming an active customer.
    """
    name = models.CharField(max_length=150)
    company_name = models.CharField(max_length=255, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    lead_source = models.CharField(max_length=100, default='WEBSITE')
    status = models.CharField(max_length=30, choices=LeadStatus.choices, default=LeadStatus.NEW, db_index=True)
    estimated_value = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    notes = models.TextField(blank=True)
    converted_customer = models.ForeignKey(
        Customer,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='originated_leads'
    )

    class Meta:
        indexes = [
            models.Index(fields=['tenant', 'status']),
        ]

    def __str__(self):
        return f"{self.name} ({self.company_name or 'Independent'})"


class Inquiry(TenantOwnedModel):
    """
    Specific freight/logistics request from a prospect or customer.
    """
    customer = models.ForeignKey(Customer, null=True, blank=True, on_delete=models.CASCADE, related_name='inquiries')
    lead = models.ForeignKey(Lead, null=True, blank=True, on_delete=models.CASCADE, related_name='inquiries')
    origin = models.CharField(max_length=255)
    destination = models.CharField(max_length=255)
    cargo_type = models.CharField(max_length=100)
    estimated_weight_kg = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    inquiry_date = models.DateField(auto_now_add=True)
    status = models.CharField(max_length=30, default='OPEN')
    notes = models.TextField(blank=True)


class Quotation(TenantOwnedModel):
    """
    Formal commercial rate quotation provided to a client.
    """
    quotation_number = models.CharField(max_length=50, db_index=True)
    customer = models.ForeignKey(Customer, null=True, blank=True, on_delete=models.CASCADE, related_name='quotations')
    lead = models.ForeignKey(Lead, null=True, blank=True, on_delete=models.CASCADE, related_name='quotations')
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    valid_until = models.DateField()
    status = models.CharField(max_length=30, choices=QuotationStatus.choices, default=QuotationStatus.DRAFT)
    terms_and_conditions = models.TextField(blank=True)


class Communication(TenantOwnedModel):
    """
    Communication log (emails, calls, meetings) with customer or lead.
    """
    customer = models.ForeignKey(Customer, null=True, blank=True, on_delete=models.CASCADE, related_name='communications')
    lead = models.ForeignKey(Lead, null=True, blank=True, on_delete=models.CASCADE, related_name='communications')
    channel = models.CharField(max_length=30, default='PHONE')  # EMAIL, PHONE, MEETING, WHATSAPP
    direction = models.CharField(max_length=20, default='OUTBOUND')  # INBOUND, OUTBOUND
    summary = models.CharField(max_length=255)
    details = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)


class FollowUp(TenantOwnedModel):
    """
    Scheduled task or reminder to follow up with a lead or customer.
    """
    customer = models.ForeignKey(Customer, null=True, blank=True, on_delete=models.CASCADE, related_name='follow_ups')
    lead = models.ForeignKey(Lead, null=True, blank=True, on_delete=models.CASCADE, related_name='follow_ups')
    due_date = models.DateField(db_index=True)
    notes = models.TextField(blank=True)
    is_completed = models.BooleanField(default=False)
