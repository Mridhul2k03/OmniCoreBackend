import random
import string
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from apps.shuttle.models import (
    ShuttleTrip, ShuttleTripStatus, ShuttleAttendance,
    AttendanceStatus, PassengerProfile, ShuttleRoute, ShuttleSchedule
)
from apps.audit.services import AuditService


class ShuttleOperationService:
    @classmethod
    @transaction.atomic
    def start_trip(cls, trip: ShuttleTrip, actor=None, notes=""):
        if trip.status not in [ShuttleTripStatus.SCHEDULED, ShuttleTripStatus.DISPATCHED]:
            raise ValidationError(f"Cannot start trip in status {trip.status}")
        
        old_status = trip.status
        trip.status = ShuttleTripStatus.IN_PROGRESS
        trip.actual_start = timezone.now()
        if notes:
            trip.notes = f"{trip.notes}\n{notes}".strip()
        trip.save(update_fields=['status', 'actual_start', 'notes', 'updated_at'])

        AuditService.record(
            action="SHUTTLE_TRIP_STARTED",
            actor=actor,
            tenant=trip.tenant,
            target_type="ShuttleTrip",
            target_id=str(trip.id),
            before_snapshot={"status": old_status},
            after_snapshot={"status": ShuttleTripStatus.IN_PROGRESS}
        )
        return trip

    @classmethod
    @transaction.atomic
    def complete_trip(cls, trip: ShuttleTrip, actor=None, notes=""):
        if trip.status != ShuttleTripStatus.IN_PROGRESS:
            raise ValidationError("Only in-progress trips can be completed.")

        trip.status = ShuttleTripStatus.COMPLETED
        trip.actual_end = timezone.now()
        if notes:
            trip.notes = f"{trip.notes}\n{notes}".strip()
        trip.save(update_fields=['status', 'actual_end', 'notes', 'updated_at'])

        AuditService.record(
            action="SHUTTLE_TRIP_COMPLETED",
            actor=actor,
            tenant=trip.tenant,
            target_type="ShuttleTrip",
            target_id=str(trip.id),
            before_snapshot={"status": ShuttleTripStatus.IN_PROGRESS},
            after_snapshot={"status": ShuttleTripStatus.COMPLETED}
        )
        return trip


    @classmethod
    @transaction.atomic
    def record_attendance(cls, trip: ShuttleTrip, passenger: PassengerProfile, status: str, stop=None, verified_by=None, notes=""):
        if status not in dict(AttendanceStatus.choices):
            raise ValidationError(f"Invalid attendance status: {status}")

        attendance, created = ShuttleAttendance.objects.update_or_create(
            tenant=trip.tenant,
            shuttle_trip=trip,
            passenger=passenger,
            defaults={
                'shuttle_stop': stop,
                'status': status,
                'verified_by': verified_by,
                'notes': notes,
            }
        )
        return attendance

    @classmethod
    @transaction.atomic
    def generate_daily_trip(cls, route: ShuttleRoute, schedule: ShuttleSchedule, trip_date, vehicle=None, driver=None):
        suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        trip_num = f"SHT-{route.route_code}-{trip_date.strftime('%Y%m%d')}-{suffix}"
        
        start_datetime = timezone.datetime.combine(trip_date, schedule.departure_time)
        if timezone.is_naive(start_datetime):
            start_datetime = timezone.make_aware(start_datetime)

        trip = ShuttleTrip.objects.create(
            tenant=route.tenant,
            trip_number=trip_num,
            shuttle_route=route,
            schedule=schedule,
            vehicle=vehicle or schedule.vehicle or route.default_vehicle,
            driver=driver or schedule.driver or route.default_driver,
            trip_date=trip_date,
            scheduled_start=start_datetime,
            status=ShuttleTripStatus.SCHEDULED
        )
        return trip
