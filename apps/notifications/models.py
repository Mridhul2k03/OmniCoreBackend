import uuid
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from apps.core.models import TenantOwnedModel


class NotificationType(models.TextChoices):
    VEHICLE_DOCUMENT_EXPIRY = 'VEHICLE_DOCUMENT_EXPIRY', _('Vehicle Document Expiry Alert')
    DRIVER_LICENSE_EXPIRY = 'DRIVER_LICENSE_EXPIRY', _('Driver License Expiry Alert')
    INSURANCE_RENEWAL = 'INSURANCE_RENEWAL', _('Insurance Renewal Notice')
    MAINTENANCE_DUE = 'MAINTENANCE_DUE', _('Vehicle Maintenance Due')
    CONTRACT_EXPIRY = 'CONTRACT_EXPIRY', _('Contract Expiry Notice')
    LOW_INVENTORY = 'LOW_INVENTORY', _('Low Inventory / Reorder Alert')
    PAYMENT_DUE = 'PAYMENT_DUE', _('Invoice Payment Due / Overdue')
    TRIP_ASSIGNMENT = 'TRIP_ASSIGNMENT', _('New Trip Assignment')
    TRIP_CHANGE = 'TRIP_CHANGE', _('Trip Status / Schedule Change')
    APPROVAL_REQUEST = 'APPROVAL_REQUEST', _('Approval Request')


class NotificationPriority(models.TextChoices):
    LOW = 'LOW', _('Low')
    MEDIUM = 'MEDIUM', _('Medium')
    HIGH = 'HIGH', _('High')
    URGENT = 'URGENT', _('Urgent')


class Notification(TenantOwnedModel):
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
        db_index=True
    )
    type = models.CharField(max_length=64, choices=NotificationType.choices, db_index=True)
    title = models.CharField(max_length=200)
    message = models.TextField()
    priority = models.CharField(max_length=20, choices=NotificationPriority.choices, default=NotificationPriority.MEDIUM)
    read_at = models.DateTimeField(null=True, blank=True, db_index=True)
    target_type = models.CharField(max_length=64, blank=True)
    target_id = models.CharField(max_length=64, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', 'recipient', 'read_at']),
            models.Index(fields=['tenant', 'type']),
        ]

    def __str__(self):
        return f"[{self.type}] {self.title} -> {self.recipient.email}"

    @property
    def is_read(self):
        return self.read_at is not None
