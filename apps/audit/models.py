import uuid
from django.db import models
from django.conf import settings


class AuditLog(models.Model):
    """
    Immutable audit trail for compliance, security, and traceability across OmniCore.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='audit_actions'
    )
    tenant = models.ForeignKey(
        'tenants.Tenant',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='audit_logs',
        db_index=True
    )
    action = models.CharField(max_length=100, db_index=True)
    target_type = models.CharField(max_length=100, db_index=True)
    target_id = models.CharField(max_length=100, blank=True, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    before_snapshot = models.JSONField(default=dict, blank=True)
    after_snapshot = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['tenant', 'timestamp']),
            models.Index(fields=['tenant', 'action']),
            models.Index(fields=['target_type', 'target_id']),
        ]

    def __str__(self):
        actor_email = self.actor.email if self.actor else 'System'
        return f"[{self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}] {actor_email} -> {self.action} on {self.target_type}:{self.target_id}"

    def save(self, *args, **kwargs):
        # Enforce immutability - once saved, audit logs cannot be modified
        if self.pk and AuditLog.objects.filter(pk=self.pk).exists():
            raise ValueError("AuditLog records are strictly immutable and cannot be updated.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("AuditLog records cannot be deleted.")
