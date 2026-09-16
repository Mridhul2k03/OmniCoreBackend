import uuid
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils.translation import gettext_lazy as _


class PlatformRole(models.TextChoices):
    NONE = 'NONE', _('None / Standard Tenant User')
    SUPER_ADMIN = 'SUPER_ADMIN', _('Super Admin (Full Platform Control)')
    SALES_ADMIN = 'SALES_ADMIN', _('Sales Admin (Leads, Proposals, Onboarding)')
    FINANCE_ADMIN = 'FINANCE_ADMIN', _('Finance Admin (Invoices, Payments, Revenue)')
    SUPPORT_ADMIN = 'SUPPORT_ADMIN', _('Support Admin (Tickets, Escalation)')
    PLATFORM_AUDITOR = 'PLATFORM_AUDITOR', _('Platform Auditor (Read-Only Audit & Reporting)')


class UserManager(BaseUserManager):
    """
    Custom user model manager where email is the unique identifier
    for authentication instead of usernames.
    """
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError(_('An email address is required.'))
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_platform_admin', True)
        extra_fields.setdefault('platform_role', PlatformRole.SUPER_ADMIN)

        if extra_fields.get('is_staff') is not True:
            raise ValueError(_('Superuser must have is_staff=True.'))
        if extra_fields.get('is_superuser') is not True:
            raise ValueError(_('Superuser must have is_superuser=True.'))

        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    """
    Primary user model for OmniCore.
    Identified globally by email and UUID.
    Can belong to multiple tenants via TenantUser memberships.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = models.CharField(max_length=150, blank=True, null=True)
    email = models.EmailField(_('email address'), unique=True, db_index=True)
    phone = models.CharField(max_length=30, blank=True)
    avatar = models.CharField(max_length=500, blank=True, null=True)
    
    # Platform admin governance
    is_platform_admin = models.BooleanField(default=False, db_index=True)
    platform_role = models.CharField(
        max_length=30,
        choices=PlatformRole.choices,
        default=PlatformRole.NONE,
        db_index=True
    )

    # MFA readiness
    is_mfa_enabled = models.BooleanField(default=False)
    mfa_secret = models.CharField(max_length=128, blank=True)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']

    class Meta:
        verbose_name = _('user')
        verbose_name_plural = _('users')
        ordering = ['-date_joined']

    def __str__(self):
        return f"{self.email} ({self.get_full_name() or 'No name'})"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip() or self.email


class UserDeviceSession(models.Model):
    """
    Tracks privileged sessions and device access for audit and security.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sessions')
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    device_name = models.CharField(max_length=100, blank=True)
    last_activity = models.DateTimeField(auto_now=True)
    is_revoked = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-last_activity']
