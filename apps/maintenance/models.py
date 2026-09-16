import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _
from apps.core.models import TenantOwnedModel


class ServiceType(models.TextChoices):
    PREVENTIVE = 'PREVENTIVE', _('Scheduled Preventive Maintenance')
    OIL_CHANGE = 'OIL_CHANGE', _('Engine Oil & Filter Replacement')
    TIRE_ROTATION = 'TIRE_ROTATION', _('Tire Rotation / Replacement')
    BRAKE_OVERHAUL = 'BRAKE_OVERHAUL', _('Brake Lining & Overhaul')
    ENGINE_REPAIR = 'ENGINE_REPAIR', _('Engine Diagnostics & Repair')
    BODYWORK = 'BODYWORK', _('Bodywork / Denting & Painting')
    OTHER = 'OTHER', _('Other Corrective Maintenance')


class RepairOrderStatus(models.TextChoices):
    OPEN = 'OPEN', _('Open')
    IN_PROGRESS = 'IN_PROGRESS', _('In Progress')
    COMPLETED = 'COMPLETED', _('Completed')
    CANCELLED = 'CANCELLED', _('Cancelled')


class MaintenanceRecord(TenantOwnedModel):
    vehicle = models.ForeignKey('fleet.Vehicle', on_delete=models.CASCADE, related_name='maintenance_records')
    service_type = models.CharField(max_length=50, choices=ServiceType.choices)
    odometer_reading = models.DecimalField(max_digits=12, decimal_places=2)
    performed_date = models.DateField(db_index=True)
    service_center = models.CharField(max_length=200, blank=True)
    cost = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    notes = models.TextField(blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['tenant', 'performed_date']),
            models.Index(fields=['tenant', 'vehicle']),
        ]

    def __str__(self):
        return f"{self.service_type} for {self.vehicle.registration_number} on {self.performed_date}"


class MaintenanceSchedule(TenantOwnedModel):
    vehicle = models.ForeignKey('fleet.Vehicle', on_delete=models.CASCADE, related_name='maintenance_schedules')
    interval_km = models.PositiveIntegerField(null=True, blank=True)
    interval_days = models.PositiveIntegerField(null=True, blank=True)
    last_service_date = models.DateField(null=True, blank=True)
    last_service_odometer = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    next_due_date = models.DateField(null=True, blank=True, db_index=True)
    next_due_odometer = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        indexes = [
            models.Index(fields=['tenant', 'next_due_date']),
        ]


class Breakdown(TenantOwnedModel):
    vehicle = models.ForeignKey('fleet.Vehicle', on_delete=models.CASCADE, related_name='breakdowns')
    driver = models.ForeignKey('drivers.Driver', null=True, blank=True, on_delete=models.SET_NULL, related_name='breakdowns')
    breakdown_date = models.DateTimeField(db_index=True)
    location = models.CharField(max_length=255)
    description = models.TextField()
    is_resolved = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(null=True, blank=True)


class Accident(TenantOwnedModel):
    vehicle = models.ForeignKey('fleet.Vehicle', on_delete=models.CASCADE, related_name='accidents')
    driver = models.ForeignKey('drivers.Driver', null=True, blank=True, on_delete=models.SET_NULL, related_name='accidents')
    accident_date = models.DateTimeField(db_index=True)
    location = models.CharField(max_length=255)
    description = models.TextField()
    estimated_damage_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    insurance_claim_number = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=30, default='REPORTED')


class RepairOrder(TenantOwnedModel):
    order_number = models.CharField(max_length=50, db_index=True)
    vehicle = models.ForeignKey('fleet.Vehicle', on_delete=models.CASCADE, related_name='repair_orders')
    issue_summary = models.CharField(max_length=255)
    status = models.CharField(max_length=30, choices=RepairOrderStatus.choices, default=RepairOrderStatus.OPEN)
    labor_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    parts_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    total_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    notes = models.TextField(blank=True)

    class Meta:
        unique_together = ('tenant', 'order_number')
