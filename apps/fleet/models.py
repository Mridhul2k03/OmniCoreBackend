import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _
from apps.core.models import TenantOwnedModel


class VehicleStatus(models.TextChoices):
    AVAILABLE = 'AVAILABLE', _('Available')
    ON_TRIP = 'ON_TRIP', _('On Trip')
    MAINTENANCE = 'MAINTENANCE', _('In Maintenance')
    INACTIVE = 'INACTIVE', _('Inactive')


class VehicleAvailability(models.TextChoices):
    AVAILABLE = 'AVAILABLE', _('Available for Dispatch')
    ASSIGNED = 'ASSIGNED', _('Assigned to Active Trip')
    UNDER_INSPECTION = 'UNDER_INSPECTION', _('Under Inspection')
    OUT_OF_SERVICE = 'OUT_OF_SERVICE', _('Out of Service')


class VehicleOwnership(models.TextChoices):
    OWNED = 'OWNED', _('Owned')
    LEASED = 'LEASED', _('Leased')
    RENTED = 'RENTED', _('Rented')
    ATTACHED = 'ATTACHED', _('Attached / Partner Fleet')


class DocumentType(models.TextChoices):
    REGISTRATION = 'REGISTRATION', _('Registration Certificate (RC)')
    INSURANCE = 'INSURANCE', _('Insurance Policy')
    FITNESS = 'FITNESS', _('Fitness Certificate')
    ROAD_TAX = 'ROAD_TAX', _('Road Tax Receipt')
    PERMIT = 'PERMIT', _('National / State Transport Permit')
    POLLUTION = 'POLLUTION', _('Pollution Under Control (PUC)')
    OTHER = 'OTHER', _('Other Compliance Document')


class DocumentStatus(models.TextChoices):
    VALID = 'VALID', _('Valid')
    EXPIRING_SOON = 'EXPIRING_SOON', _('Expiring Soon')
    EXPIRED = 'EXPIRED', _('Expired')
    PENDING_RENEWAL = 'PENDING_RENEWAL', _('Pending Renewal')


class VehicleCategory(TenantOwnedModel):
    """
    Vehicle classifications (Heavy Haul, Prime Mover, 32ft Container, Reefer, Light Commercial).
    """
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=50)
    description = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = 'Vehicle Categories'
        unique_together = ('tenant', 'code')

    def __str__(self):
        return self.name


class Vehicle(TenantOwnedModel):
    """
    Core vehicle entity in OmniCore fleet ecosystem.
    """
    registration_number = models.CharField(max_length=50, db_index=True)
    category = models.ForeignKey(VehicleCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name='vehicles')
    make = models.CharField(max_length=100)
    model = models.CharField(max_length=100)
    year = models.PositiveIntegerField(null=True, blank=True)
    vin_number = models.CharField(max_length=100, blank=True)
    status = models.CharField(
        max_length=30,
        choices=VehicleStatus.choices,
        default=VehicleStatus.AVAILABLE,
        db_index=True
    )
    availability = models.CharField(
        max_length=30,
        choices=VehicleAvailability.choices,
        default=VehicleAvailability.AVAILABLE,
        db_index=True
    )
    ownership = models.CharField(
        max_length=30,
        choices=VehicleOwnership.choices,
        default=VehicleOwnership.OWNED
    )
    odometer = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    fuel_type = models.CharField(max_length=50, default='DIESEL')
    payload_capacity_kg = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    class Meta:
        ordering = ['-created_at']
        unique_together = ('tenant', 'registration_number')
        indexes = [
            models.Index(fields=['tenant', 'status']),
            models.Index(fields=['tenant', 'availability']),
            models.Index(fields=['tenant', 'registration_number']),
        ]

    def __str__(self):
        return f"{self.registration_number} - {self.make} {self.model}"


class VehicleDocument(TenantOwnedModel):
    """
    Compliance and regulatory documents attached to a vehicle.
    """
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name='documents')
    document_type = models.CharField(max_length=50, choices=DocumentType.choices)
    document_number = models.CharField(max_length=100)
    issue_date = models.DateField()
    expiry_date = models.DateField(db_index=True)
    file_path = models.CharField(max_length=500, blank=True, help_text="S3 tenant-scoped storage path")
    status = models.CharField(
        max_length=30,
        choices=DocumentStatus.choices,
        default=DocumentStatus.VALID,
        db_index=True
    )
    notes = models.TextField(blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['tenant', 'expiry_date']),
            models.Index(fields=['tenant', 'status']),
        ]

    def __str__(self):
        return f"{self.get_document_type_display()} for {self.vehicle.registration_number} (Exp: {self.expiry_date})"


class VehicleAssignment(TenantOwnedModel):
    """
    Historical log of vehicle assignments to drivers or business units.
    """
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name='assignments')
    driver = models.ForeignKey('drivers.Driver', on_delete=models.CASCADE, null=True, blank=True, related_name='vehicle_assignments')
    assigned_from = models.DateTimeField()
    assigned_to = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['tenant', 'is_active']),
        ]
