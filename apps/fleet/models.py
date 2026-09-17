import uuid
from django.db import models
from django.core.exceptions import ValidationError
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


class VehicleVertical(models.TextChoices):
    TAXI_CAB = 'taxi_cab', _('Taxi / Cab')
    TOURIST_BUS = 'tourist_bus', _('Tourist Bus')
    FREIGHT_LOGISTICS = 'freight_logistics', _('Freight Logistics')
    PACKERS_MOVERS = 'packers_movers', _('Packers & Movers')
    B2B_CONTRACT = 'b2b_contract', _('B2B Contract')
    COLD_CHAIN = 'cold_chain', _('Cold Chain')
    LAST_MILE = 'last_mile', _('Last Mile')
    HEAVY_MACHINERY = 'heavy_machinery', _('Heavy Machinery')
    COURIER_EXPRESS = 'courier_express', _('Courier Express')
    CORPORATE_SHUTTLE = 'corporate_shuttle', _('Corporate Shuttle')
    ALL_VERTICALS = 'all_verticals', _('All Verticals')


class VehicleType(models.TextChoices):
    SEDAN = 'sedan', _('Sedan')
    SUV = 'suv', _('SUV')
    BUS = 'bus', _('Bus')
    MINI_TRUCK = 'mini_truck', _('Mini Truck')
    HEAVY_TRUCK = 'heavy_truck', _('Heavy Truck')
    REEFER_COLD = 'reefer_cold', _('Reefer / Cold Storage')
    FLATBED = 'flatbed', _('Flatbed')
    CONTAINER = 'container', _('Container')


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


class Branch(TenantOwnedModel):
    """
    Operating branch, depot, or regional base for fleet vehicles.
    """
    name = models.CharField(max_length=150)
    code = models.CharField(max_length=50, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    address = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = 'Branches'
        unique_together = ('tenant', 'code')
        indexes = [
            models.Index(fields=['tenant', 'name']),
            models.Index(fields=['tenant', 'is_active']),
        ]

    def __str__(self):
        return f"{self.name} ({self.code})" if self.code else self.name


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
    branch = models.ForeignKey(Branch, on_delete=models.SET_NULL, null=True, blank=True, related_name='vehicles')
    assigned_driver = models.ForeignKey(
        'drivers.Driver',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_vehicles'
    )
    vertical = models.CharField(
        max_length=50,
        choices=VehicleVertical.choices,
        default=VehicleVertical.FREIGHT_LOGISTICS,
        db_index=True
    )
    type = models.CharField(
        max_length=50,
        choices=VehicleType.choices,
        default=VehicleType.HEAVY_TRUCK,
        db_index=True
    )
    make = models.CharField(max_length=100)
    model = models.CharField(max_length=100)
    year = models.PositiveIntegerField(null=True, blank=True)
    vin = models.CharField(max_length=100, blank=True)
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
    odometer_km = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    fuel_type = models.CharField(max_length=50, default='DIESEL')
    capacity_kg = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    temperature_sensor = models.JSONField(null=True, blank=True, default=dict)
    fuel_level_percent = models.DecimalField(max_digits=5, decimal_places=2, default=100.00)
    engine_oil_life_percent = models.DecimalField(max_digits=5, decimal_places=2, default=100.00)
    ad_blue_level_percent = models.DecimalField(max_digits=5, decimal_places=2, default=100.00, null=True, blank=True)

    # Legacy Aliases / Properties
    @property
    def vin_number(self):
        return self.vin

    @vin_number.setter
    def vin_number(self, value):
        self.vin = value

    @property
    def odometer(self):
        return self.odometer_km

    @odometer.setter
    def odometer(self, value):
        self.odometer_km = value

    @property
    def payload_capacity_kg(self):
        return self.capacity_kg

    @payload_capacity_kg.setter
    def payload_capacity_kg(self, value):
        self.capacity_kg = value

    class Meta:
        ordering = ['-created_at']
        unique_together = ('tenant', 'registration_number')
        indexes = [
            models.Index(fields=['tenant', 'status']),
            models.Index(fields=['tenant', 'availability']),
            models.Index(fields=['tenant', 'registration_number']),
            models.Index(fields=['tenant', 'vertical']),
            models.Index(fields=['tenant', 'type']),
        ]

    def __str__(self):
        return f"{self.registration_number} - {self.make} {self.model}"

    def clean(self):
        super().clean()
        # Driver guarding: prevent reassigning or removing assigned_driver while vehicle status is on_trip
        if self.pk:
            current = Vehicle.objects.filter(pk=self.pk).values('assigned_driver_id', 'status').first()
            if current and str(current['status']).lower() == 'on_trip':
                if current['assigned_driver_id'] != self.assigned_driver_id:
                    raise ValidationError({
                        'assigned_driver': _("Cannot reassign or remove driver while vehicle status is 'on_trip'.")
                    })

    def save(self, *args, **kwargs):
        # Driver guarding check on save as well
        if self.pk:
            current = Vehicle.objects.filter(pk=self.pk).values('assigned_driver_id', 'status').first()
            if current and str(current['status']).lower() == 'on_trip':
                if current['assigned_driver_id'] != self.assigned_driver_id:
                    raise ValidationError(_("Cannot reassign or remove driver while vehicle status is 'on_trip'."))

        # Map legacy update_fields names to new field names
        if 'update_fields' in kwargs and kwargs['update_fields'] is not None:
            fields = set(kwargs['update_fields'])
            if 'odometer' in fields:
                fields.remove('odometer')
                fields.add('odometer_km')
            if 'vin_number' in fields:
                fields.remove('vin_number')
                fields.add('vin')
            if 'payload_capacity_kg' in fields:
                fields.remove('payload_capacity_kg')
                fields.add('capacity_kg')
            kwargs['update_fields'] = list(fields)

        super().save(*args, **kwargs)


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
