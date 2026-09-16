import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _
from apps.core.models import TenantOwnedModel


class DriverStatus(models.TextChoices):
    AVAILABLE = 'AVAILABLE', _('Available for Duty')
    ON_TRIP = 'ON_TRIP', _('On Active Trip')
    ON_LEAVE = 'ON_LEAVE', _('On Leave')
    RESTING = 'RESTING', _('Resting / Off Duty')
    SUSPENDED = 'SUSPENDED', _('Suspended')
    INACTIVE = 'INACTIVE', _('Inactive')


class IncidentSeverity(models.TextChoices):
    LOW = 'LOW', _('Low Severity')
    MEDIUM = 'MEDIUM', _('Medium Severity')
    HIGH = 'HIGH', _('High Severity')
    CRITICAL = 'CRITICAL', _('Critical Incident')


class Driver(TenantOwnedModel):
    """
    Driver profile in OmniCore.
    """
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=30, db_index=True)
    email = models.EmailField(blank=True)
    license_number = models.CharField(max_length=100, db_index=True)
    license_type = models.CharField(max_length=50, default='HEAVY_MOTOR_VEHICLE')
    license_expiry = models.DateField(db_index=True)
    status = models.CharField(
        max_length=30,
        choices=DriverStatus.choices,
        default=DriverStatus.AVAILABLE,
        db_index=True
    )
    current_vehicle = models.ForeignKey(
        'fleet.Vehicle',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='current_drivers'
    )
    emergency_contact_name = models.CharField(max_length=100, blank=True)
    emergency_contact_phone = models.CharField(max_length=30, blank=True)
    date_of_joining = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        unique_together = ('tenant', 'license_number')
        indexes = [
            models.Index(fields=['tenant', 'status']),
            models.Index(fields=['tenant', 'license_expiry']),
            models.Index(fields=['tenant', 'license_number']),
        ]

    def __str__(self):
        return f"{self.first_name} {self.last_name} (Lic: {self.license_number})"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"


class DriverDocument(TenantOwnedModel):
    """
    Regulatory and compliance documents for a driver (license, medical, background checks).
    """
    driver = models.ForeignKey(Driver, on_delete=models.CASCADE, related_name='documents')
    document_type = models.CharField(max_length=50)
    document_number = models.CharField(max_length=100)
    issue_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True, db_index=True)
    file_path = models.CharField(max_length=500, blank=True)
    is_verified = models.BooleanField(default=False)

    class Meta:
        indexes = [
            models.Index(fields=['tenant', 'expiry_date']),
        ]

    def __str__(self):
        return f"{self.document_type} for {self.driver.full_name}"


class DriverAssignment(TenantOwnedModel):
    """
    Record of a driver assigned to a specific vehicle or fleet group.
    """
    driver = models.ForeignKey(Driver, on_delete=models.CASCADE, related_name='assignments')
    vehicle = models.ForeignKey('fleet.Vehicle', on_delete=models.CASCADE, related_name='driver_assignments')
    assigned_from = models.DateTimeField()
    assigned_to = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        indexes = [
            models.Index(fields=['tenant', 'is_active']),
        ]


class Attendance(TenantOwnedModel):
    """
    Driver daily shift attendance and duty check-in/out.
    """
    driver = models.ForeignKey(Driver, on_delete=models.CASCADE, related_name='attendance_records')
    date = models.DateField(db_index=True)
    check_in_time = models.DateTimeField(null=True, blank=True)
    check_out_time = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=30, default='PRESENT')  # PRESENT, ABSENT, LEAVE, HALF_DAY
    notes = models.TextField(blank=True)

    class Meta:
        unique_together = ('tenant', 'driver', 'date')
        indexes = [
            models.Index(fields=['tenant', 'date']),
        ]


class DriverIncident(TenantOwnedModel):
    """
    Accidents, traffic violations, or behavioral infractions logged for a driver.
    """
    driver = models.ForeignKey(Driver, on_delete=models.CASCADE, related_name='incidents')
    vehicle = models.ForeignKey('fleet.Vehicle', on_delete=models.SET_NULL, null=True, blank=True, related_name='driver_incidents')
    incident_date = models.DateTimeField(db_index=True)
    severity = models.CharField(max_length=30, choices=IncidentSeverity.choices, default=IncidentSeverity.LOW)
    location = models.CharField(max_length=255, blank=True)
    description = models.TextField()
    action_taken = models.TextField(blank=True)
    fine_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    class Meta:
        indexes = [
            models.Index(fields=['tenant', 'incident_date']),
            models.Index(fields=['tenant', 'severity']),
        ]
