from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from apps.core.models import TenantOwnedModel


class ShuttleOrgType(models.TextChoices):
    SCHOOL = 'SCHOOL', _('School / Academic Institution')
    CORPORATE = 'CORPORATE', _('Corporate / Enterprise Employer')


class ShuttleDirection(models.TextChoices):
    INBOUND = 'INBOUND', _('Inbound (Pickup to Campus/Office)')
    OUTBOUND = 'OUTBOUND', _('Outbound (Drop from Campus/Office)')
    ROUND_TRIP = 'ROUND_TRIP', _('Round Trip Loop')


class PassengerType(models.TextChoices):
    STUDENT = 'STUDENT', _('Student')
    EMPLOYEE = 'EMPLOYEE', _('Corporate Employee')


class ShuttleTripStatus(models.TextChoices):
    SCHEDULED = 'SCHEDULED', _('Scheduled')
    DISPATCHED = 'DISPATCHED', _('Dispatched')
    IN_PROGRESS = 'IN_PROGRESS', _('In Progress')
    COMPLETED = 'COMPLETED', _('Completed')
    CANCELLED = 'CANCELLED', _('Cancelled')


class AttendanceStatus(models.TextChoices):
    BOARDED = 'BOARDED', _('Boarded Shuttle')
    ALIGHTED = 'ALIGHTED', _('Alighted Safely')
    ABSENT = 'ABSENT', _('Absent')
    EXCUSED = 'EXCUSED', _('Excused Absence')


class ShuttleOrganization(TenantOwnedModel):
    """
    Client educational institution or enterprise contracting shuttle transit services.
    """
    org_type = models.CharField(max_length=20, choices=ShuttleOrgType.choices, default=ShuttleOrgType.CORPORATE)
    name = models.CharField(max_length=150)
    code = models.CharField(max_length=50, db_index=True)
    contact_person = models.CharField(max_length=150)
    contact_email = models.EmailField()
    contact_phone = models.CharField(max_length=30)
    address = models.TextField()
    configuration = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']
        unique_together = ('tenant', 'code')
        indexes = [
            models.Index(fields=['tenant', 'code']),
            models.Index(fields=['tenant', 'org_type']),
        ]

    def __str__(self):
        return f"{self.name} [{self.org_type}]"


class ShuttleRoute(TenantOwnedModel):
    """
    Dedicated shuttle corridor linking designated stops with organization campus/office.
    Reuses or references base trips.Route if applicable.
    """
    organization = models.ForeignKey(ShuttleOrganization, on_delete=models.CASCADE, related_name='routes')
    base_route = models.ForeignKey('trips.Route', null=True, blank=True, on_delete=models.SET_NULL, related_name='shuttle_routes')
    route_name = models.CharField(max_length=150)
    route_code = models.CharField(max_length=50, db_index=True)
    direction = models.CharField(max_length=20, choices=ShuttleDirection.choices, default=ShuttleDirection.INBOUND)
    start_location = models.CharField(max_length=255)
    end_location = models.CharField(max_length=255)
    default_vehicle = models.ForeignKey('fleet.Vehicle', null=True, blank=True, on_delete=models.SET_NULL, related_name='default_shuttle_routes')
    default_driver = models.ForeignKey('drivers.Driver', null=True, blank=True, on_delete=models.SET_NULL, related_name='default_shuttle_routes')
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['route_code']
        unique_together = ('tenant', 'route_code')
        indexes = [
            models.Index(fields=['tenant', 'organization']),
            models.Index(fields=['tenant', 'route_code']),
        ]

    def __str__(self):
        return f"{self.route_code}: {self.route_name} ({self.organization.name})"


class ShuttleStop(TenantOwnedModel):
    """
    Geocoded pickup/drop-off point along a shuttle route.
    """
    shuttle_route = models.ForeignKey(ShuttleRoute, on_delete=models.CASCADE, related_name='stops')
    stop_name = models.CharField(max_length=150)
    sequence = models.PositiveIntegerField(default=1)
    landmark = models.CharField(max_length=255, blank=True)
    latitude = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    scheduled_offset_minutes = models.IntegerField(default=0, help_text="Minutes offset from trip start time")

    class Meta:
        ordering = ['sequence']
        unique_together = ('shuttle_route', 'sequence')

    def __str__(self):
        return f"Stop #{self.sequence}: {self.stop_name} ({self.shuttle_route.route_code})"


class ShuttleSchedule(TenantOwnedModel):
    """
    Recurring timetable for a shuttle route.
    """
    shuttle_route = models.ForeignKey(ShuttleRoute, on_delete=models.CASCADE, related_name='schedules')
    day_of_week = models.CharField(max_length=20, default='WEEKDAYS', help_text="MON, TUE, WED, THU, FRI, WEEKDAYS, or ALL")
    departure_time = models.TimeField()
    estimated_arrival_time = models.TimeField()
    vehicle = models.ForeignKey('fleet.Vehicle', null=True, blank=True, on_delete=models.SET_NULL)
    driver = models.ForeignKey('drivers.Driver', null=True, blank=True, on_delete=models.SET_NULL)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['departure_time']

    def __str__(self):
        return f"{self.shuttle_route.route_code} @ {self.departure_time} ({self.day_of_week})"


class PassengerProfile(TenantOwnedModel):
    """
    Student or corporate employee passenger enrolled in shuttle services.
    """
    organization = models.ForeignKey(ShuttleOrganization, on_delete=models.CASCADE, related_name='passengers')
    passenger_type = models.CharField(max_length=20, choices=PassengerType.choices, default=PassengerType.EMPLOYEE)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    id_number = models.CharField(max_length=50, db_index=True, help_text="Roll number or employee badge ID")
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30)
    pickup_stop = models.ForeignKey(ShuttleStop, null=True, blank=True, on_delete=models.SET_NULL, related_name='pickup_passengers')
    dropoff_stop = models.ForeignKey(ShuttleStop, null=True, blank=True, on_delete=models.SET_NULL, related_name='dropoff_passengers')
    emergency_contact_name = models.CharField(max_length=150, blank=True)
    emergency_contact_phone = models.CharField(max_length=30, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['last_name', 'first_name']
        unique_together = ('tenant', 'organization', 'id_number')
        indexes = [
            models.Index(fields=['tenant', 'id_number']),
            models.Index(fields=['tenant', 'organization']),
        ]

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.id_number})"


class ShuttleAssignment(TenantOwnedModel):
    """
    Seat allocation mapping a passenger to an active shuttle route and timeframe.
    """
    passenger = models.ForeignKey(PassengerProfile, on_delete=models.CASCADE, related_name='route_assignments')
    shuttle_route = models.ForeignKey(ShuttleRoute, on_delete=models.CASCADE, related_name='passenger_assignments')
    seat_number = models.CharField(max_length=20, blank=True)
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-effective_from']
        indexes = [
            models.Index(fields=['tenant', 'passenger']),
            models.Index(fields=['tenant', 'shuttle_route']),
        ]

    def __str__(self):
        return f"{self.passenger} -> {self.shuttle_route.route_code}"


class ShuttleTrip(TenantOwnedModel):
    """
    Daily operational execution run of a scheduled shuttle route.
    """
    trip_number = models.CharField(max_length=50, db_index=True)
    shuttle_route = models.ForeignKey(ShuttleRoute, on_delete=models.CASCADE, related_name='operational_trips')
    schedule = models.ForeignKey(ShuttleSchedule, null=True, blank=True, on_delete=models.SET_NULL)
    vehicle = models.ForeignKey('fleet.Vehicle', null=True, blank=True, on_delete=models.SET_NULL, related_name='shuttle_trips')
    driver = models.ForeignKey('drivers.Driver', null=True, blank=True, on_delete=models.SET_NULL, related_name='shuttle_trips')
    trip_date = models.DateField(db_index=True)
    scheduled_start = models.DateTimeField()
    actual_start = models.DateTimeField(null=True, blank=True)
    actual_end = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=30,
        choices=ShuttleTripStatus.choices,
        default=ShuttleTripStatus.SCHEDULED,
        db_index=True
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-trip_date', '-scheduled_start']
        unique_together = ('tenant', 'trip_number')
        indexes = [
            models.Index(fields=['tenant', 'trip_date', 'status']),
            models.Index(fields=['tenant', 'shuttle_route']),
        ]

    def __str__(self):
        return f"{self.trip_number} - {self.shuttle_route.route_code} ({self.trip_date})"


class ShuttleAttendance(TenantOwnedModel):
    """
    Boarding and alighting verification record for a passenger on a specific shuttle trip.
    """
    shuttle_trip = models.ForeignKey(ShuttleTrip, on_delete=models.CASCADE, related_name='attendance_records')
    passenger = models.ForeignKey(PassengerProfile, on_delete=models.CASCADE, related_name='attendance_history')
    shuttle_stop = models.ForeignKey(ShuttleStop, null=True, blank=True, on_delete=models.SET_NULL)
    status = models.CharField(max_length=20, choices=AttendanceStatus.choices, default=AttendanceStatus.BOARDED)
    timestamp = models.DateTimeField(auto_now_add=True)
    verified_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-timestamp']
        unique_together = ('shuttle_trip', 'passenger')
        indexes = [
            models.Index(fields=['tenant', 'shuttle_trip', 'status']),
        ]

    def __str__(self):
        return f"{self.passenger} on {self.shuttle_trip.trip_number}: {self.status}"
