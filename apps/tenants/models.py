import uuid
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from apps.core.models import TimeStampedModel, SoftDeleteModel


class TenantStatus(models.TextChoices):
    DRAFT = 'DRAFT', _('Draft')
    PROVISIONING = 'PROVISIONING', _('Provisioning')
    ACTIVE = 'ACTIVE', _('Active')
    TRIAL = 'TRIAL', _('Trial')
    GRACE_PERIOD = 'GRACE_PERIOD', _('Grace Period')
    SUSPENDED = 'SUSPENDED', _('Suspended')
    CANCELLED = 'CANCELLED', _('Cancelled')
    ARCHIVED = 'ARCHIVED', _('Archived')


class TenantRoleCode(models.TextChoices):
    TENANT_ADMIN = 'TENANT_ADMIN', _('Tenant Administrator')
    OPERATIONS_MANAGER = 'OPERATIONS_MANAGER', _('Operations Manager')
    FLEET_MANAGER = 'FLEET_MANAGER', _('Fleet Manager')
    FINANCE_USER = 'FINANCE_USER', _('Finance & Billing User')
    HR_USER = 'HR_USER', _('HR & Payroll User')
    WAREHOUSE_USER = 'WAREHOUSE_USER', _('Warehouse & Inventory User')
    SALES_CRM_USER = 'SALES_CRM_USER', _('Sales & CRM User')
    DRIVER_FIELD_USER = 'DRIVER_FIELD_USER', _('Driver & Field User')


class Vertical(TimeStampedModel):
    """
    Industry verticals served by OmniCore (e.g., Freight Logistics, Cold Chain, Oil & Gas).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=64, unique=True, db_index=True)
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Tenant(TimeStampedModel, SoftDeleteModel):
    """
    Core Tenant entity. Represents an isolated enterprise company/organization.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant_id = models.CharField(max_length=64, unique=True, db_index=True, help_text="Public ID e.g. OCT-100234")
    company_name = models.CharField(max_length=255, db_index=True)
    slug = models.SlugField(max_length=100, unique=True, db_index=True)
    email = models.EmailField()
    phone = models.CharField(max_length=30, blank=True)
    address = models.TextField(blank=True)
    logo = models.CharField(max_length=500, blank=True, null=True)
    status = models.CharField(
        max_length=32,
        choices=TenantStatus.choices,
        default=TenantStatus.DRAFT,
        db_index=True
    )
    verticals = models.ManyToManyField(Vertical, blank=True, related_name='tenants')
    package = models.ForeignKey(
        'subscriptions.Package',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='tenants'
    )
    activated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at']),
        ]

    def __str__(self):
        return f"{self.company_name} ({self.tenant_id})"


class Role(TimeStampedModel):
    """
    Role definition for RBAC. Can be platform-seeded system role or custom tenant role.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='roles',
        help_text="Null for global system default roles"
    )
    code = models.CharField(max_length=64, db_index=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    is_system_role = models.BooleanField(default=False)

    class Meta:
        unique_together = ('tenant', 'code')

    def __str__(self):
        return f"{self.name} ({self.code})"


class Permission(TimeStampedModel):
    """
    Granular permission item (e.g. 'vehicle.create', 'trip.dispatch', 'invoice.approve').
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=100, unique=True, db_index=True)
    name = models.CharField(max_length=150)
    module = models.CharField(max_length=64, db_index=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['module', 'code']

    def __str__(self):
        return f"{self.module} -> {self.code}"


class RolePermission(TimeStampedModel):
    """
    Mapping between Role and Permission.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name='role_permissions')
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE, related_name='permission_roles')

    class Meta:
        unique_together = ('role', 'permission')


class TenantUser(TimeStampedModel):
    """
    Associates a User with a Tenant, along with their assigned Role and permissions.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='memberships')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='tenant_memberships')
    role = models.ForeignKey(Role, null=True, blank=True, on_delete=models.SET_NULL, related_name='assigned_tenant_users')
    is_primary = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    custom_permissions = models.ManyToManyField(Permission, blank=True, related_name='custom_tenant_users')

    class Meta:
        unique_together = ('tenant', 'user')
        indexes = [
            models.Index(fields=['tenant', 'user', 'is_active']),
        ]

    def __str__(self):
        return f"{self.user.email} in {self.tenant.company_name} ({self.role.name if self.role else 'No Role'})"

    def get_all_permissions(self):
        """
        Returns a list of all permission codes granted to this tenant membership.
        """
        if self.role and self.role.code == 'TENANT_ADMIN':
            return list(Permission.objects.values_list('code', flat=True))

        perms = set()
        if self.role:
            perms.update(
                self.role.role_permissions.values_list('permission__code', flat=True)
            )
        perms.update(
            self.custom_permissions.values_list('code', flat=True)
        )
        return list(perms)
