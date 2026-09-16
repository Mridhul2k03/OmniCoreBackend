import uuid
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from apps.core.models import TimeStampedModel


class PackageTier(models.TextChoices):
    BASIC = 'BASIC', _('Basic (Core operations & essentials)')
    STANDARD = 'STANDARD', _('Standard (Fleet, maintenance & finance)')
    CORPORATE = 'CORPORATE', _('Corporate (Contracts, CRM, HR, Warehouse)')
    ENTERPRISE = 'ENTERPRISE', _('Enterprise (Full ecosystem, analytics, integrations)')


class BillingCycle(models.TextChoices):
    MONTHLY = 'MONTHLY', _('Monthly')
    YEARLY = 'YEARLY', _('Yearly')


class SubscriptionStatus(models.TextChoices):
    TRIAL = 'TRIAL', _('Trial')
    ACTIVE = 'ACTIVE', _('Active')
    PAST_DUE = 'PAST_DUE', _('Past Due')
    CANCELLED = 'CANCELLED', _('Cancelled')
    EXPIRED = 'EXPIRED', _('Expired')


class Feature(TimeStampedModel):
    """
    Catalog of granular platform capabilities and modules.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=64, unique=True, db_index=True)
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=64, default='core')

    def __str__(self):
        return f"{self.name} ({self.code})"


class Package(TimeStampedModel):
    """
    SaaS subscription packages (BASIC, STANDARD, CORPORATE, ENTERPRISE).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=32, choices=PackageTier.choices, unique=True, db_index=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    price_monthly = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    price_yearly = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    max_vehicles = models.IntegerField(null=True, blank=True, help_text="Null for unlimited")
    max_users = models.IntegerField(null=True, blank=True, help_text="Null for unlimited")
    is_active = models.BooleanField(default=True)
    features = models.ManyToManyField(Feature, through='PackageFeature', related_name='packages')

    def __str__(self):
        return f"{self.name} ({self.code})"


class PackageFeature(TimeStampedModel):
    """
    Through-model mapping features included in a package.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    package = models.ForeignKey(Package, on_delete=models.CASCADE, related_name='package_features')
    feature = models.ForeignKey(Feature, on_delete=models.CASCADE, related_name='feature_packages')
    limit_value = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        unique_together = ('package', 'feature')


class Addon(TimeStampedModel):
    """
    Configurable add-on modules that can be attached to any package.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=64, unique=True, db_index=True)
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    monthly_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    features = models.ManyToManyField(Feature, related_name='addons')
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} (+${self.monthly_price}/mo)"


class TenantFeature(TimeStampedModel):
    """
    Represents the active entitlement of a feature for a specific tenant.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.CASCADE, related_name='tenant_features')
    feature = models.ForeignKey(Feature, on_delete=models.CASCADE, related_name='tenant_entitlements')
    is_enabled = models.BooleanField(default=True)
    source = models.CharField(max_length=32, default='PACKAGE')  # PACKAGE, ADDON, CUSTOM

    class Meta:
        unique_together = ('tenant', 'feature')
        indexes = [
            models.Index(fields=['tenant', 'is_enabled']),
        ]


class Subscription(TimeStampedModel):
    """
    Active subscription contract for a tenant.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.OneToOneField('tenants.Tenant', on_delete=models.CASCADE, related_name='subscription')
    package = models.ForeignKey(Package, on_delete=models.PROTECT, related_name='subscriptions')
    addons = models.ManyToManyField(Addon, blank=True, related_name='subscriptions')
    billing_cycle = models.CharField(max_length=20, choices=BillingCycle.choices, default=BillingCycle.MONTHLY)
    status = models.CharField(max_length=20, choices=SubscriptionStatus.choices, default=SubscriptionStatus.ACTIVE)
    current_period_start = models.DateTimeField()
    current_period_end = models.DateTimeField()
    trial_end = models.DateTimeField(null=True, blank=True)
    auto_renew = models.BooleanField(default=True)

    def __str__(self):
        return f"Sub for {self.tenant.company_name} ({self.package.name} - {self.status})"


class TenantFeatureOverride(TimeStampedModel):
    """
    Allows Super Admins to grant or revoke an isolated feature for a specific tenant
    without modifying the tenant's underlying baseline package or global package definitions.
    Supports time-limited overrides with automatic expiry.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.CASCADE, related_name='feature_overrides')
    feature = models.ForeignKey(Feature, on_delete=models.CASCADE, related_name='overrides')
    enabled = models.BooleanField(default=True, help_text="True to grant/unlock, False to explicitly revoke")
    reason = models.TextField(blank=True, help_text="Operational rationale for custom feature override")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    expires_at = models.DateTimeField(null=True, blank=True, help_text="Optional expiry date for temporary features")
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        unique_together = ('tenant', 'feature')
        indexes = [
            models.Index(fields=['tenant', 'enabled']),
            models.Index(fields=['tenant', 'expires_at']),
        ]

    def __str__(self):
        status_str = "ENABLED" if self.enabled else "DISABLED"
        return f"[{status_str}] {self.feature.code} for {self.tenant.company_name}"

    @property
    def is_expired(self):
        from django.utils import timezone
        if self.expires_at and self.expires_at < timezone.now():
            return True
        return False

