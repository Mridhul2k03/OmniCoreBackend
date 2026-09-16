from django.db import transaction
from django.utils import timezone
from apps.trips.models import Trip, TripStatus
from apps.fleet.models import VehicleStatus, VehicleAvailability
from apps.drivers.models import DriverStatus
from apps.core.exceptions import BusinessValidationError
from apps.audit.services import AuditService


class TripWorkflowService:
    """
    Guarantees state machine correctness, fleet/driver resource locking,
    and billing handoff across the trip lifecycle.
    """
    VALID_TRANSITIONS = {
        TripStatus.REQUESTED: [TripStatus.SCHEDULED, TripStatus.CONFIRMED, TripStatus.CANCELLED],
        TripStatus.SCHEDULED: [TripStatus.CONFIRMED, TripStatus.DISPATCHED, TripStatus.CANCELLED],
        TripStatus.CONFIRMED: [TripStatus.DISPATCHED, TripStatus.CANCELLED],
        TripStatus.DISPATCHED: [TripStatus.STARTED, TripStatus.CANCELLED],
        TripStatus.STARTED: [TripStatus.IN_PROGRESS, TripStatus.COMPLETED, TripStatus.CANCELLED],
        TripStatus.IN_PROGRESS: [TripStatus.COMPLETED, TripStatus.CANCELLED],
        TripStatus.COMPLETED: [TripStatus.BILLING_READY],
        TripStatus.BILLING_READY: [],
        TripStatus.CANCELLED: [],
    }

    @classmethod
    def transition(cls, trip: Trip, target_status: str, actor=None, extra_data=None) -> Trip:
        extra_data = extra_data or {}
        current_status = trip.status

        allowed = cls.VALID_TRANSITIONS.get(current_status, [])
        if target_status not in allowed:
            raise BusinessValidationError(
                f"Invalid trip status transition from '{current_status}' to '{target_status}'. Allowed: {allowed}",
                code='INVALID_STATE_TRANSITION'
            )

        with transaction.atomic():
            old_snapshot = {'status': trip.status, 'vehicle': str(trip.vehicle_id), 'driver': str(trip.driver_id)}

            if target_status == TripStatus.DISPATCHED:
                if not trip.vehicle:
                    raise BusinessValidationError("Cannot dispatch trip without an assigned vehicle.")
                if not trip.driver:
                    raise BusinessValidationError("Cannot dispatch trip without an assigned driver.")

                # Lock vehicle and driver
                trip.vehicle.status = VehicleStatus.ON_TRIP
                trip.vehicle.availability = VehicleAvailability.ASSIGNED
                trip.vehicle.save(update_fields=['status', 'availability'])

                trip.driver.status = DriverStatus.ON_TRIP
                trip.driver.save(update_fields=['status'])

            elif target_status == TripStatus.STARTED:
                trip.actual_start = extra_data.get('actual_start') or timezone.now()
                if 'start_odometer' in extra_data:
                    trip.start_odometer = extra_data['start_odometer']

            elif target_status == TripStatus.COMPLETED:
                trip.actual_end = extra_data.get('actual_end') or timezone.now()
                if 'end_odometer' in extra_data:
                    trip.end_odometer = extra_data['end_odometer']
                    if trip.start_odometer:
                        trip.distance_km = max(0, float(trip.end_odometer) - float(trip.start_odometer))
                    if trip.vehicle:
                        trip.vehicle.odometer = trip.end_odometer

                # Release vehicle and driver
                if trip.vehicle:
                    trip.vehicle.status = VehicleStatus.AVAILABLE
                    trip.vehicle.availability = VehicleAvailability.AVAILABLE
                    trip.vehicle.save(update_fields=['status', 'availability', 'odometer'])

                if trip.driver:
                    trip.driver.status = DriverStatus.AVAILABLE
                    trip.driver.save(update_fields=['status'])

            elif target_status == TripStatus.CANCELLED:
                # Release resources if previously locked
                if trip.vehicle and trip.vehicle.status == VehicleStatus.ON_TRIP:
                    trip.vehicle.status = VehicleStatus.AVAILABLE
                    trip.vehicle.availability = VehicleAvailability.AVAILABLE
                    trip.vehicle.save(update_fields=['status', 'availability'])

                if trip.driver and trip.driver.status == DriverStatus.ON_TRIP:
                    trip.driver.status = DriverStatus.AVAILABLE
                    trip.driver.save(update_fields=['status'])

            trip.status = target_status
            trip.save()

            AuditService.record(
                action='TRIP_STATUS_TRANSITION',
                actor=actor,
                tenant=trip.tenant,
                target_type='Trip',
                target_id=str(trip.id),
                before_snapshot=old_snapshot,
                after_snapshot={'status': trip.status},
                metadata=extra_data
            )

            return trip
