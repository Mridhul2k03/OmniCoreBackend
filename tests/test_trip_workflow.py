from rest_framework.test import APITestCase
from apps.tenants.services import TenantProvisioningService
from apps.fleet.models import Vehicle, VehicleStatus, VehicleAvailability
from apps.drivers.models import Driver, DriverStatus
from apps.crm.models import Customer
from apps.trips.models import Trip, TripStatus
from apps.trips.services import TripWorkflowService
from apps.core.exceptions import BusinessValidationError


class TripWorkflowTests(APITestCase):
    def setUp(self):
        self.tenant_data = TenantProvisioningService.provision(
            company_name="Express Line Haul",
            admin_email="ops@expresshaul.com",
            admin_password="Password123!",
            package_code="CORPORATE"
        )
        self.tenant = self.tenant_data['tenant']
        self.user = self.tenant_data['admin_user']

        self.customer = Customer.objects.create(
            tenant=self.tenant,
            company_name="Major Retailer Ltd"
        )
        self.vehicle = Vehicle.objects.create(
            tenant=self.tenant,
            registration_number="EXP-TRUCK-01",
            odometer=50000.00,
            status=VehicleStatus.AVAILABLE
        )
        self.driver = Driver.objects.create(
            tenant=self.tenant,
            first_name="David",
            last_name="Miller",
            license_number="DL-998877",
            license_expiry="2028-12-31",
            status=DriverStatus.AVAILABLE
        )
        self.trip = Trip.objects.create(
            tenant=self.tenant,
            trip_number="TRIP-1001",
            customer=self.customer,
            vehicle=self.vehicle,
            driver=self.driver,
            origin="Dallas, TX",
            destination="Houston, TX",
            freight_charge=1500.00,
            status=TripStatus.REQUESTED
        )

    def test_complete_trip_lifecycle(self):
        # 1. Confirm and Dispatch
        TripWorkflowService.transition(self.trip, TripStatus.CONFIRMED, actor=self.user)
        TripWorkflowService.transition(self.trip, TripStatus.DISPATCHED, actor=self.user)
        self.vehicle.refresh_from_db()
        self.driver.refresh_from_db()
        self.assertEqual(self.trip.status, TripStatus.DISPATCHED)
        self.assertEqual(self.vehicle.status, VehicleStatus.ON_TRIP)
        self.assertEqual(self.vehicle.availability, VehicleAvailability.ASSIGNED)
        self.assertEqual(self.driver.status, DriverStatus.ON_TRIP)

        # 2. Start
        TripWorkflowService.transition(
            self.trip,
            TripStatus.STARTED,
            actor=self.user,
            extra_data={'start_odometer': 50000.00}
        )
        self.assertEqual(self.trip.status, TripStatus.STARTED)
        self.assertEqual(float(self.trip.start_odometer), 50000.00)
        self.assertIsNotNone(self.trip.actual_start)

        # 3. Complete
        TripWorkflowService.transition(
            self.trip,
            TripStatus.COMPLETED,
            actor=self.user,
            extra_data={'end_odometer': 50380.00}
        )
        self.vehicle.refresh_from_db()
        self.driver.refresh_from_db()
        self.assertEqual(self.trip.status, TripStatus.COMPLETED)
        self.assertEqual(float(self.trip.distance_km), 380.00)
        self.assertEqual(float(self.vehicle.odometer), 50380.00)

        # Vehicle and driver released
        self.assertEqual(self.vehicle.status, VehicleStatus.AVAILABLE)
        self.assertEqual(self.vehicle.availability, VehicleAvailability.AVAILABLE)
        self.assertEqual(self.driver.status, DriverStatus.AVAILABLE)

    def test_illegal_state_jump_rejected(self):
        """
        Attempting to transition from REQUESTED directly to COMPLETED must raise BusinessValidationError.
        """
        with self.assertRaises(BusinessValidationError):
            TripWorkflowService.transition(self.trip, TripStatus.COMPLETED, actor=self.user)
