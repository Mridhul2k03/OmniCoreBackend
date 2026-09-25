import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone


class TimeStampedModel(models.Model):
    """
    Abstract base model that provides self-updating
    created_at and updated_at fields.
    """
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class TenantAwareQuerySet(models.QuerySet):
    """
    Custom queryset for tenant-owned models that enforces soft-delete filtering.
    """
    def delete(self):
        return self.update(is_deleted=True, deleted_at=timezone.now())

    def hard_delete(self):
        return super().delete()

    def alive(self):
        return self.filter(is_deleted=False)

    def deleted(self):
        return self.filter(is_deleted=True)


class TenantAwareManager(models.Manager):
    """
    Default manager that excludes soft-deleted records.
    """
    def get_queryset(self):
        return TenantAwareQuerySet(self.model, using=self._db).filter(is_deleted=False)

    def all_with_deleted(self):
        return TenantAwareQuerySet(self.model, using=self._db)

    def deleted_only(self):
        return TenantAwareQuerySet(self.model, using=self._db).filter(is_deleted=True)


class SoftDeleteModel(models.Model):
    """
    Abstract model enabling safe soft deletion of enterprise records.
    """
    is_deleted = models.BooleanField(default=False, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = TenantAwareManager()
    all_objects = models.Manager()

    class Meta:
        abstract = True

    def delete(self, using=None, keep_parents=False):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(update_fields=['is_deleted', 'deleted_at'])

    def hard_delete(self, using=None, keep_parents=False):
        super().delete(using=using, keep_parents=keep_parents)

    def restore(self):
        self.is_deleted = False
        self.deleted_at = None
        self.save(update_fields=['is_deleted', 'deleted_at'])


class TenantBaseModel(TimeStampedModel, SoftDeleteModel):
    """
    Abstract base model for all tenant-scoped business entities in OmniCore.
    Enforces tenant association, created_at/updated_at timestamps, created_by attribution,
    and composite indexing.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name="%(class)ss",
        db_index=True
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='%(app_label)s_%(class)s_created'
    )

    class Meta:
        abstract = True
        indexes = [
            models.Index(fields=['tenant', 'created_at']),
            models.Index(fields=['tenant', 'is_deleted']),
        ]


# Backward compatibility alias
TenantOwnedModel = TenantBaseModel

