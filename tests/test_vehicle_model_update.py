from rest_framework.test import APITestCase
from django.core.exceptions import ValidationError
from apps.tenants.services import TenantProvisioningService
from apps.fleet.models import (
    Vehicle,
    VehicleStatus,
    VehicleAvailability,
    VehicleVertical,
    VehicleType,
    Branch,
)
from apps.drivers.models import Driver, DriverStatus
from apps.fleet.serializers import VehicleSerializer, BranchSerializer


class VehicleModelUpdateTests(APITestCase):
    def setUp(self):
        self.tenant_data = TenantProvisioningService.provision(
            company_name="Apex Global Logistics",
            admin_email="fleetops@apex.com",
            admin_password="Password123!",
            package_code="ENTERPRISE"
        )
        self.tenant = self.tenant_data['tenant']
        self.user = self.tenant_data['admin_user']

        # Create Drivers
        self.driver1 = Driver.objects.create(
            tenant=self.tenant,
            first_name="Carlos",
            last_name="Mendoza",
            license_number="DL-MEND-01",
            license_expiry="2028-12-31",
            status=DriverStatus.AVAILABLE
        )
        self.driver2 = Driver.objects.create(
            tenant=self.tenant,
            first_name="Darius",
            last_name="Jackson",
            license_number="DL-JACK-02",
            license_expiry="2028-12-31",
            status=DriverStatus.AVAILABLE
        )

        # Create Branch
        self.branch = Branch.objects.create(
            tenant=self.tenant,
            name="Chicago Central Depot",
            code="CHI-01",
            city="Chicago",
            state="IL"
        )

    def test_create_vehicle_with_all_new_fields(self):
        """Test vehicle creation with branch, assigned_driver, vertical, type, and telemetry fields."""
        vehicle = Vehicle.objects.create(
            tenant=self.tenant,
            registration_number="IL-9428-TX",
            make="Volvo",
            model="FH16 750",
            year=2024,
            vin="YV2RT40A5MA109823",
            branch=self.branch,
            assigned_driver=self.driver1,
            vertical=VehicleVertical.COLD_CHAIN,
            type=VehicleType.REEFER_COLD,
            odometer_km=84320.50,
            capacity_kg=24000.00,
            fuel_level_percent=78.50,
            engine_oil_life_percent=92.00,
            ad_blue_level_percent=85.00,
            temperature_sensor={
                "currentTempC": -19.4,
                "targetTempC": -20.0,
                "humidityPercent": 62,
                "status": "normal"
            }
        )

        self.assertEqual(vehicle.branch, self.branch)
        self.assertEqual(vehicle.assigned_driver, self.driver1)
        self.assertEqual(vehicle.vertical, "cold_chain")
        self.assertEqual(vehicle.type, "reefer_cold")
        self.assertEqual(float(vehicle.odometer_km), 84320.50)
        self.assertEqual(float(vehicle.capacity_kg), 24000.00)
        self.assertEqual(float(vehicle.fuel_level_percent), 78.50)
        self.assertEqual(float(vehicle.engine_oil_life_percent), 92.00)
        self.assertEqual(float(vehicle.ad_blue_level_percent), 85.00)
        self.assertEqual(vehicle.temperature_sensor["currentTempC"], -19.4)

    def test_renaming_and_aliases_on_model(self):
        """Test backward-compatible properties and setters for vin_number, odometer, and payload_capacity_kg."""
        vehicle = Vehicle(
            tenant=self.tenant,
            registration_number="ALIAS-TEST-01",
            make="Freightliner",
            model="Cascadia",
        )
        # Set using legacy names
        vehicle.vin_number = "1FUJBBCK4NL892019"
        vehicle.odometer = 55000.25
        vehicle.payload_capacity_kg = 30000.00
        vehicle.save()

        # Check that underlying fields were updated
        self.assertEqual(vehicle.vin, "1FUJBBCK4NL892019")
        self.assertEqual(float(vehicle.odometer_km), 55000.25)
        self.assertEqual(float(vehicle.capacity_kg), 30000.00)

        # Check that legacy properties return the values
        self.assertEqual(vehicle.vin_number, "1FUJBBCK4NL892019")
        self.assertEqual(float(vehicle.odometer), 55000.25)
        self.assertEqual(float(vehicle.payload_capacity_kg), 30000.00)

        # Test save with legacy field names in update_fields
        vehicle.odometer = 56000.00
        vehicle.save(update_fields=['odometer'])
        vehicle.refresh_from_db()
        self.assertEqual(float(vehicle.odometer_km), 56000.00)

    def test_serializer_representation_and_aliases(self):
        """Test serializer outputs both new names and legacy aliases, and includes helper names."""
        vehicle = Vehicle.objects.create(
            tenant=self.tenant,
            registration_number="SER-TEST-01",
            make="Scania",
            model="R500",
            vin="SCANIA998877",
            branch=self.branch,
            assigned_driver=self.driver1,
            vertical=VehicleVertical.FREIGHT_LOGISTICS,
            type=VehicleType.HEAVY_TRUCK,
            odometer_km=12000.00,
            capacity_kg=28000.00,
            fuel_level_percent=95.00
        )

        serializer = VehicleSerializer(instance=vehicle)
        data = serializer.data

        # Verify new fields
        self.assertEqual(data['vin'], "SCANIA998877")
        self.assertEqual(float(data['odometer_km']), 12000.00)
        self.assertEqual(float(data['capacity_kg']), 28000.00)
        self.assertEqual(str(data['branch']), str(self.branch.id))
        self.assertEqual(data['branch_name'], "Chicago Central Depot")
        self.assertEqual(str(data['assigned_driver']), str(self.driver1.id))
        self.assertEqual(data['assigned_driver_name'], "Carlos Mendoza")

        # Verify legacy aliases in output
        self.assertEqual(data['vin_number'], "SCANIA998877")
        self.assertEqual(float(data['odometer']), 12000.00)
        self.assertEqual(float(data['payload_capacity_kg']), 28000.00)

    def test_serializer_input_with_aliases(self):
        """Test serializer deserialization accepts legacy field names."""
        payload = {
            'registration_number': "DESER-TEST-01",
            'make': "Kenworth",
            'model': "T680",
            'vin_number': "KW8839210",
            'odometer': "42000.50",
            'payload_capacity_kg': "25000.00",
            'vertical': 'freight_logistics',
            'type': 'heavy_truck',
            'assigned_driver': str(self.driver1.id),
        }
        serializer = VehicleSerializer(data=payload)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data['vin'], "KW8839210")
        self.assertEqual(float(serializer.validated_data['odometer_km']), 42000.50)
        self.assertEqual(float(serializer.validated_data['capacity_kg']), 25000.00)

    def test_driver_guarding_when_available(self):
        """Reassigning driver is permitted when vehicle is available."""
        vehicle = Vehicle.objects.create(
            tenant=self.tenant,
            registration_number="GUARD-AVAIL-01",
            make="Volvo",
            model="FH",
            status=VehicleStatus.AVAILABLE,
            assigned_driver=self.driver1
        )

        # Reassign to driver 2
        vehicle.assigned_driver = self.driver2
        vehicle.full_clean()
        vehicle.save()
        vehicle.refresh_from_db()
        self.assertEqual(vehicle.assigned_driver, self.driver2)

        # Serializer reassign
        serializer = VehicleSerializer(
            instance=vehicle,
            data={'assigned_driver': str(self.driver1.id)},
            partial=True
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_driver_guarding_when_on_trip(self):
        """Prevent reassigning or unassigning driver while vehicle status is on_trip."""
        vehicle = Vehicle.objects.create(
            tenant=self.tenant,
            registration_number="GUARD-TRIP-01",
            make="Volvo",
            model="FH",
            status=VehicleStatus.ON_TRIP,
            assigned_driver=self.driver1
        )

        # 1. Model clean() should fail when changing driver
        vehicle.assigned_driver = self.driver2
        with self.assertRaises(ValidationError):
            vehicle.full_clean()

        # 2. Model save() should fail when changing driver
        with self.assertRaises(ValidationError):
            vehicle.save()

        # 3. Model save() should fail when removing driver
        vehicle.assigned_driver = None
        with self.assertRaises(ValidationError):
            vehicle.save()

        # 4. Serializer validation should fail
        vehicle.refresh_from_db()
        serializer = VehicleSerializer(
            instance=vehicle,
            data={'assigned_driver': str(self.driver2.id)},
            partial=True
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn('assigned_driver', serializer.errors)

    def test_updating_telemetry_while_on_trip_succeeds(self):
        """Updating telemetry (odometer, fuel, temp) while on trip is allowed."""
        vehicle = Vehicle.objects.create(
            tenant=self.tenant,
            registration_number="TELEMETRY-TRIP-01",
            make="Volvo",
            model="FH",
            status=VehicleStatus.ON_TRIP,
            assigned_driver=self.driver1,
            odometer_km=10000.00,
            fuel_level_percent=80.00
        )

        # Update odometer and fuel while driver remains unchanged
        vehicle.odometer_km = 10150.00
        vehicle.fuel_level_percent = 74.00
        vehicle.temperature_sensor = {"currentTempC": -20.1}
        vehicle.full_clean()
        vehicle.save()

        vehicle.refresh_from_db()
        self.assertEqual(float(vehicle.odometer_km), 10150.00)
        self.assertEqual(float(vehicle.fuel_level_percent), 74.00)
        self.assertEqual(vehicle.temperature_sensor["currentTempC"], -20.1)
        self.assertEqual(vehicle.assigned_driver, self.driver1)

    def test_api_create_and_filter_vehicles(self):
        """Test API creation of vehicles and filtering with status=all&vertical=all."""
        self.client.force_authenticate(user=self.user)

        # 1. Test POST /api/v1/fleet/vehicles/
        create_payload = {
            "registration_number": "API-POST-99",
            "make": "Freightliner",
            "model": "Cascadia",
            "year": 2024,
            "vin": "1FUJBBCK4NL100200",
            "vertical": "freight_logistics",
            "type": "heavy_truck",
            "odometer_km": "15000.00",
            "capacity_kg": "26000.00",
            "fuel_level_percent": "90.00",
            "branch": str(self.branch.id),
            "assigned_driver": str(self.driver1.id),
        }
        response = self.client.post(
            "/api/v1/fleet/vehicles/",
            data=create_payload,
            format="json",
            HTTP_X_TENANT_ID=str(self.tenant.id)
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["registration_number"], "API-POST-99")
        self.assertEqual(response.data["vin"], "1FUJBBCK4NL100200")
        self.assertEqual(response.data["branch_name"], "Chicago Central Depot")
        self.assertEqual(response.data["assigned_driver_name"], "Carlos Mendoza")

        # 2. Test GET /api/v1/fleet/vehicles/?status=all&vertical=all (must return 200 OK)
        get_response = self.client.get(
            "/api/v1/fleet/vehicles/?status=all&vertical=all",
            HTTP_X_TENANT_ID=str(self.tenant.id)
        )
        self.assertEqual(get_response.status_code, 200, get_response.data)
        self.assertGreaterEqual(len(get_response.data), 1)

