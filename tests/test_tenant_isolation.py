from rest_framework.test import APITestCase
from rest_framework import status
from apps.tenants.services import TenantProvisioningService
from apps.tenants.models import TenantStatus
from apps.fleet.models import Vehicle, VehicleStatus
from apps.crm.models import Customer
from apps.finance.models import Invoice


class TenantIsolationTests(APITestCase):
    """
    CRITICAL SECURITY & MULTI-TENANCY TEST SUITE
    Verifies that cross-tenant access is strictly denied at the backend level.
    """
    def setUp(self):
        # 1. Provision Tenant A
        self.tenant_a_data = TenantProvisioningService.provision(
            company_name="Logistics Alpha Corp",
            admin_email="admin@alpha.com",
            admin_password="Password123!",
            package_code="CORPORATE"
        )
        self.tenant_a = self.tenant_a_data['tenant']
        self.user_a = self.tenant_a_data['admin_user']

        # 2. Provision Tenant B
        self.tenant_b_data = TenantProvisioningService.provision(
            company_name="Beta Transport Fleet",
            admin_email="admin@beta.com",
            admin_password="Password123!",
            package_code="CORPORATE"
        )
        self.tenant_b = self.tenant_b_data['tenant']
        self.user_b = self.tenant_b_data['admin_user']

        # 3. Create Resources for Tenant A
        self.vehicle_a = Vehicle.objects.create(
            tenant=self.tenant_a,
            registration_number="ALPHA-001",
            make="Volvo",
            model="FH16",
            status=VehicleStatus.AVAILABLE
        )
        self.customer_a = Customer.objects.create(
            tenant=self.tenant_a,
            company_name="Alpha Shipper Ltd",
            is_active=True
        )

        # 4. Create Resources for Tenant B
        self.vehicle_b = Vehicle.objects.create(
            tenant=self.tenant_b,
            registration_number="BETA-999",
            make="Scania",
            model="R500",
            status=VehicleStatus.AVAILABLE
        )
        self.customer_b = Customer.objects.create(
            tenant=self.tenant_b,
            company_name="Beta Shipper LLC",
            is_active=True
        )

    def test_list_isolation(self):
        """
        Tenant A listing vehicles must ONLY see Tenant A vehicles.
        Tenant B vehicles must never be exposed.
        """
        self.client.force_authenticate(user=self.user_a)
        response = self.client.get(
            '/api/v1/vehicles/',
            HTTP_X_TENANT_ID=self.tenant_a.tenant_id
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get('data', response.data.get('results', []))
        vehicle_regs = [v['registration_number'] for v in results]
        self.assertIn("ALPHA-001", vehicle_regs)
        self.assertNotIn("BETA-999", vehicle_regs)

    def test_retrieve_cross_tenant_denied(self):
        """
        Tenant A attempting to retrieve Tenant B's vehicle by UUID must fail with 404.
        """
        self.client.force_authenticate(user=self.user_a)
        response = self.client.get(
            f'/api/v1/vehicles/{self.vehicle_b.id}/',
            HTTP_X_TENANT_ID=self.tenant_a.tenant_id
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(response.data['success'])
        self.assertEqual(response.data['error']['code'], 'RESOURCE_NOT_FOUND')

    def test_update_cross_tenant_denied(self):
        """
        Tenant A attempting to update Tenant B's vehicle must fail with 404.
        """
        self.client.force_authenticate(user=self.user_a)
        response = self.client.patch(
            f'/api/v1/vehicles/{self.vehicle_b.id}/',
            {'model': 'HackedModel'},
            HTTP_X_TENANT_ID=self.tenant_a.tenant_id
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.vehicle_b.refresh_from_db()
        self.assertEqual(self.vehicle_b.model, "R500")

    def test_delete_cross_tenant_denied(self):
        """
        Tenant A attempting to delete Tenant B's vehicle must fail with 404.
        """
        self.client.force_authenticate(user=self.user_a)
        response = self.client.delete(
            f'/api/v1/vehicles/{self.vehicle_b.id}/',
            HTTP_X_TENANT_ID=self.tenant_a.tenant_id
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(Vehicle.objects.filter(id=self.vehicle_b.id, is_deleted=False).exists())

    def test_create_ignores_tampered_tenant_in_body(self):
        """
        Creating a vehicle while injecting Tenant B's ID in the body must still
        save the vehicle under Tenant A (the authenticated context).
        """
        self.client.force_authenticate(user=self.user_a)
        response = self.client.post(
            '/api/v1/vehicles/',
            {
                'registration_number': 'ALPHA-NEW-100',
                'make': 'Mercedes',
                'model': 'Actros',
                'tenant': str(self.tenant_b.id)  # Attacking: attempting to assign to Tenant B
            },
            HTTP_X_TENANT_ID=self.tenant_a.tenant_id
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created_vehicle = Vehicle.objects.get(registration_number='ALPHA-NEW-100')
        # Crucial check: belongs to Tenant A, NOT Tenant B
        self.assertEqual(created_vehicle.tenant, self.tenant_a)

    def test_suspended_tenant_access_blocked(self):
        """
        When a tenant is SUSPENDED, all operational APIs must return 403 TENANT_NOT_ACTIVE.
        """
        self.tenant_a.status = TenantStatus.SUSPENDED
        self.tenant_a.save()

        self.client.force_authenticate(user=self.user_a)
        response = self.client.get(
            '/api/v1/vehicles/',
            HTTP_X_TENANT_ID=self.tenant_a.tenant_id
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data['error']['code'], 'TENANT_NOT_ACTIVE')
