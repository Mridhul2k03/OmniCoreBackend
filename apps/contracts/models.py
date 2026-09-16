import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _
from apps.core.models import TenantOwnedModel


class TenderStatus(models.TextChoices):
    OPEN = 'OPEN', _('Open for Bidding')
    BID_SUBMITTED = 'BID_SUBMITTED', _('Bid Submitted')
    EVALUATION = 'EVALUATION', _('Under Evaluation')
    AWARDED = 'AWARDED', _('Awarded / Won')
    LOST = 'LOST', _('Lost')


class ProposalStatus(models.TextChoices):
    DRAFT = 'DRAFT', _('Draft Proposal')
    SUBMITTED = 'SUBMITTED', _('Submitted')
    NEGOTIATION = 'NEGOTIATION', _('In Negotiation')
    ACCEPTED = 'ACCEPTED', _('Accepted')
    REJECTED = 'REJECTED', _('Rejected')


class ContractStatus(models.TextChoices):
    DRAFT = 'DRAFT', _('Draft')
    PENDING_APPROVAL = 'PENDING_APPROVAL', _('Pending Legal/Finance Approval')
    ACTIVE = 'ACTIVE', _('Active Execution')
    RENEWAL_DUE = 'RENEWAL_DUE', _('Renewal Due')
    EXPIRED = 'EXPIRED', _('Expired')
    TERMINATED = 'TERMINATED', _('Terminated')


class Tender(TenantOwnedModel):
    tender_number = models.CharField(max_length=100, db_index=True)
    title = models.CharField(max_length=255)
    issuing_authority = models.CharField(max_length=255)
    submission_deadline = models.DateTimeField(db_index=True)
    estimated_value = models.DecimalField(max_digits=14, decimal_places=2, default=0.00)
    status = models.CharField(max_length=30, choices=TenderStatus.choices, default=TenderStatus.OPEN, db_index=True)
    scope_of_work = models.TextField(blank=True)

    class Meta:
        unique_together = ('tenant', 'tender_number')

    def __str__(self):
        return f"{self.tender_number} - {self.title}"


class Proposal(TenantOwnedModel):
    proposal_number = models.CharField(max_length=100, db_index=True)
    tender = models.ForeignKey(Tender, null=True, blank=True, on_delete=models.SET_NULL, related_name='proposals')
    customer = models.ForeignKey('crm.Customer', on_delete=models.CASCADE, related_name='proposals')
    quoted_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0.00)
    submission_date = models.DateField()
    valid_until = models.DateField()
    status = models.CharField(max_length=30, choices=ProposalStatus.choices, default=ProposalStatus.DRAFT, db_index=True)
    commercial_terms = models.TextField(blank=True)

    class Meta:
        unique_together = ('tenant', 'proposal_number')

    def __str__(self):
        return f"Proposal {self.proposal_number} for {self.customer.company_name}"


class Contract(TenantOwnedModel):
    contract_number = models.CharField(max_length=100, db_index=True)
    title = models.CharField(max_length=255)
    customer = models.ForeignKey('crm.Customer', on_delete=models.CASCADE, related_name='contracts')
    proposal = models.ForeignKey(Proposal, null=True, blank=True, on_delete=models.SET_NULL, related_name='contracts')
    start_date = models.DateField(db_index=True)
    end_date = models.DateField(db_index=True)
    total_contract_value = models.DecimalField(max_digits=14, decimal_places=2, default=0.00)
    minimum_monthly_commitment = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    payment_terms_days = models.PositiveIntegerField(default=30)
    status = models.CharField(max_length=30, choices=ContractStatus.choices, default=ContractStatus.DRAFT, db_index=True)
    terms_and_conditions = models.TextField(blank=True)

    class Meta:
        unique_together = ('tenant', 'contract_number')
        indexes = [
            models.Index(fields=['tenant', 'status']),
            models.Index(fields=['tenant', 'end_date']),
        ]

    def __str__(self):
        return f"{self.contract_number} - {self.title} ({self.customer.company_name})"


class ContractDocument(TenantOwnedModel):
    contract = models.ForeignKey(Contract, on_delete=models.CASCADE, related_name='documents')
    document_title = models.CharField(max_length=200)
    document_type = models.CharField(max_length=50, default='SIGNED_AGREEMENT')
    file_path = models.CharField(max_length=500)
    uploaded_at = models.DateTimeField(auto_now_add=True)


class ContractAllocation(TenantOwnedModel):
    contract = models.ForeignKey(Contract, on_delete=models.CASCADE, related_name='allocations')
    vehicle_category = models.ForeignKey('fleet.VehicleCategory', on_delete=models.SET_NULL, null=True, blank=True)
    committed_vehicles = models.PositiveIntegerField(default=1)
    agreed_rate_per_km = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)
    agreed_monthly_fixed = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)


class ContractTrip(TenantOwnedModel):
    contract = models.ForeignKey(Contract, on_delete=models.CASCADE, related_name='contract_trips')
    trip = models.OneToOneField('trips.Trip', on_delete=models.CASCADE, related_name='contract_attribution')
    billing_amount = models.DecimalField(max_digits=12, decimal_places=2)
    attributed_date = models.DateField(auto_now_add=True)
