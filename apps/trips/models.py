import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _
from apps.core.models import TenantOwnedModel


class BookingStatus(models.TextChoices):
    DRAFT = 'DRAFT', _('Draft')
    CONFIRMED = 'CONFIRMED', _('Confirmed')
    ALLOCATED = 'ALLOCATED', _('Allocated to Trip')
    CANCELLED = 'CANCELLED', _('Cancelled')


class TripStatus(models.TextChoices):
    REQUESTED = 'REQUESTED', _('Requested')
    SCHEDULED = 'SCHEDULED', _('Scheduled')
    CONFIRMED = 'CONFIRMED', _('Confirmed')
    DISPATCHED = 'DISPATCHED', _('Dispatched')
    STARTED = 'STARTED', _('Started')
    IN_PROGRESS = 'IN_PROGRESS', _('In Progress')
    COMPLETED = 'COMPLETED', _('Completed')
    BILLING_READY = 'BILLING_READY', _('Billing Ready')
    CANCELLED = 'CANCELLED', _('Cancelled')


class TripExpenseType(models.TextChoices):
    FUEL = 'FUEL', _('Fuel Refill')
    TOLL = 'TOLL', _('Highway Toll')
    DRIVER = 'DRIVER', _('Driver Allowance / Daily Batta')
    PARKING = 'PARKING', _('Parking Fee')
    OTHER = 'OTHER', _('Other Incidental Expense')


class Booking(TenantOwnedModel):
    """
    Shipper booking request prior to or during trip allocation.
    """
    booking_number = models.CharField(max_length=50, db_index=True)
    customer = models.ForeignKey('crm.Customer', on_delete=models.CASCADE, related_name='bookings')
    pickup_location = models.CharField(max_length=255)
    dropoff_location = models.CharField(max_length=255)
    cargo_type = models.CharField(max_length=100)
    cargo_weight_kg = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    scheduled_date = models.DateField(db_index=True)
    commercial_rate = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    status = models.CharField(
        max_length=30,
        choices=BookingStatus.choices,
        default=BookingStatus.CONFIRMED,
        db_index=True
    )
    notes = models.TextField(blank=True)

    class Meta:
        unique_together = ('tenant', 'booking_number')
        indexes = [
            models.Index(fields=['tenant', 'status']),
            models.Index(fields=['tenant', 'scheduled_date']),
        ]

    def __str__(self):
        return f"{self.booking_number} - {self.customer.company_name}"


class Route(TenantOwnedModel):
    """
    Predefined or recurring transport corridor/route.
    """
    name = models.CharField(max_length=150)
    origin = models.CharField(max_length=255)
    destination = models.CharField(max_length=255)
    standard_distance_km = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    estimated_hours = models.DecimalField(max_digits=6, decimal_places=2, default=0.00)
    toll_points_count = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ('tenant', 'name')

    def __str__(self):
        return f"{self.name} ({self.origin} -> {self.destination})"


class Trip(TenantOwnedModel):
    """
    Central freight trip execution entity.
    Tracks vehicle, driver, lifecycle state machine, and billing inputs.
    """
    trip_number = models.CharField(max_length=50, db_index=True)
    customer = models.ForeignKey('crm.Customer', on_delete=models.CASCADE, related_name='trips')
    booking = models.ForeignKey(Booking, null=True, blank=True, on_delete=models.SET_NULL, related_name='trips')
    vehicle = models.ForeignKey('fleet.Vehicle', null=True, blank=True, on_delete=models.SET_NULL, related_name='trips')
    driver = models.ForeignKey('drivers.Driver', null=True, blank=True, on_delete=models.SET_NULL, related_name='trips')
    route = models.ForeignKey(Route, null=True, blank=True, on_delete=models.SET_NULL, related_name='trips')
    origin = models.CharField(max_length=255)
    destination = models.CharField(max_length=255)
    
    # Timing
    scheduled_start = models.DateTimeField(null=True, blank=True)
    scheduled_end = models.DateTimeField(null=True, blank=True)
    actual_start = models.DateTimeField(null=True, blank=True)
    actual_end = models.DateTimeField(null=True, blank=True)
    
    # Odometers & distance
    start_odometer = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    end_odometer = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    distance_km = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    # Commercials
    freight_charge = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    advance_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    detention_charges = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    
    status = models.CharField(
        max_length=30,
        choices=TripStatus.choices,
        default=TripStatus.REQUESTED,
        db_index=True
    )
    notes = models.TextField(blank=True)

    class Meta:
        unique_together = ('tenant', 'trip_number')
        indexes = [
            models.Index(fields=['tenant', 'status']),
            models.Index(fields=['tenant', 'actual_start']),
            models.Index(fields=['tenant', 'customer']),
        ]

    def __str__(self):
        return f"Trip {self.trip_number} ({self.origin} -> {self.destination}) [{self.status}]"


class TripExpense(TenantOwnedModel):
    """
    On-road operational expense logged against an active or completed trip.
    """
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name='expenses')
    expense_type = models.CharField(max_length=30, choices=TripExpenseType.choices)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    receipt_number = models.CharField(max_length=100, blank=True)
    receipt_file = models.CharField(max_length=500, blank=True)
    notes = models.TextField(blank=True)
    is_approved = models.BooleanField(default=False)

    class Meta:
        indexes = [
            models.Index(fields=['tenant', 'expense_type']),
        ]
