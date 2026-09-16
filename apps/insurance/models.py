import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _
from apps.core.models import TenantOwnedModel


class PolicyType(models.TextChoices):
    COMPREHENSIVE = 'COMPREHENSIVE', _('Comprehensive Commercial Fleet')
    THIRD_PARTY = 'THIRD_PARTY', _('Third Party Liability')
    CARGO = 'CARGO', _('Marine & Cargo Transit')
    HEALTH = 'HEALTH', _('Group Driver & Employee Health')


class ClaimStatus(models.TextChoices):
    SUBMITTED = 'SUBMITTED', _('Claim Submitted')
    UNDER_SURVEY = 'UNDER_SURVEY', _('Under Surveyor Assessment')
    APPROVED = 'APPROVED', _('Approved by Insurer')
    SETTLED = 'SETTLED', _('Funds Disbursed & Settled')
    REJECTED = 'REJECTED', _('Claim Rejected')


class InsurancePolicy(TenantOwnedModel):
    policy_number = models.CharField(max_length=100, db_index=True)
    provider_name = models.CharField(max_length=200)
    policy_type = models.CharField(max_length=50, choices=PolicyType.choices, default=PolicyType.COMPREHENSIVE)
    vehicle = models.ForeignKey('fleet.Vehicle', null=True, blank=True, on_delete=models.SET_NULL, related_name='insurance_policies')
    start_date = models.DateField()
    end_date = models.DateField(db_index=True)
    premium_amount = models.DecimalField(max_digits=12, decimal_places=2)
    coverage_amount = models.DecimalField(max_digits=14, decimal_places=2)
    status = models.CharField(max_length=30, default='ACTIVE', db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=['tenant', 'end_date']),
            models.Index(fields=['tenant', 'status']),
        ]

    def __str__(self):
        return f"{self.policy_number} - {self.provider_name} (Exp: {self.end_date})"


class InsuranceClaim(TenantOwnedModel):
    claim_number = models.CharField(max_length=100, db_index=True)
    policy = models.ForeignKey(InsurancePolicy, on_delete=models.CASCADE, related_name='claims')
    incident_date = models.DateField(db_index=True)
    claim_amount = models.DecimalField(max_digits=12, decimal_places=2)
    approved_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    status = models.CharField(max_length=30, choices=ClaimStatus.choices, default=ClaimStatus.SUBMITTED, db_index=True)
    surveyor_name = models.CharField(max_length=150, blank=True)
    notes = models.TextField(blank=True)


class LegalDocument(TenantOwnedModel):
    title = models.CharField(max_length=200)
    document_type = models.CharField(max_length=50)
    reference_number = models.CharField(max_length=100, blank=True)
    effective_date = models.DateField()
    expiry_date = models.DateField(null=True, blank=True)
    file_path = models.CharField(max_length=500)
    status = models.CharField(max_length=30, default='ACTIVE')


class ComplianceRecord(TenantOwnedModel):
    regulation_name = models.CharField(max_length=200)
    authority = models.CharField(max_length=150)
    compliance_status = models.CharField(max_length=30, default='COMPLIANT')
    audit_date = models.DateField()
    next_due_date = models.DateField(db_index=True)
    notes = models.TextField(blank=True)
