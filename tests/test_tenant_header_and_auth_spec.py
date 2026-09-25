import uuid
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from apps.accounts.models import PlatformRole
from apps.tenants.models import Tenant, TenantUser
from apps.tenants.services import TenantProvisioningService
from apps.subscriptions.models import Package, PackageTier
from apps.fleet.models import Vehicle, VehicleStatus
from apps.core.models import TenantBaseModel, TenantOwnedModel

User = get_user_model()


class TenantHeaderAndAuthSpecTests(APITestCase):
    def setUp(self):
        # 1. Packages
        Package.objects.get_or_create(
            code=PackageTier.BASIC,
            defaults={'name': 'Basic', 'price_monthly': 149.00, 'price_yearly': 1490.00}
        )
        Package.objects.get_or_create(
            code=PackageTier.STANDARD,
            defaults={'name': 'Standard', 'price_monthly': 399.00, 'price_yearly': 3990.00}
        )
        Package.objects.get_or_create(
            code=PackageTier.CORPORATE,
            defaults={'name': 'Corporate', 'price_monthly': 899.00, 'price_yearly': 8990.00}
        )

        # 2. Provision Tenant A
        self.tenant_a_data = TenantProvisioningService.provision(
            company_name="Apex Global Logistics",
            admin_email="alex.morgan@apex.com",
            admin_password="SuperPassword123!",
            admin_first_name="Alex",
            admin_last_name="Morgan",
            package_code="STANDARD"
        )
        self.tenant_a = self.tenant_a_data['tenant']
        self.user_a = self.tenant_a_data['admin_user']

        # 3. Provision Tenant B
        self.tenant_b_data = TenantProvisioningService.provision(
            company_name="Beacon Freight Systems",
            admin_email="bob@beacon.com",
            admin_password="SuperPassword123!",
            admin_first_name="Bob",
            admin_last_name="Builder",
            package_code="STANDARD"
        )
        self.tenant_b = self.tenant_b_data['tenant']
        self.user_b = self.tenant_b_data['admin_user']

        # 4. Super Admin User (No Tenant)
        self.super_admin = User.objects.create_superuser(
            email="platform.admin@omnicore.io",
            password="SuperAdminPassword123!",
            first_name="Platform",
            last_name="SuperAdmin"
        )

        # 5. Create vehicles under Tenant A and B
        self.vehicle_a = Vehicle.objects.create(
            tenant=self.tenant_a,
            registration_number="APEX-101",
            make="Volvo",
            model="FH16",
            status=VehicleStatus.AVAILABLE
        )
        self.vehicle_b = Vehicle.objects.create(
            tenant=self.tenant_b,
            registration_number="BEACON-202",
            make="Scania",
            model="R500",
            status=VehicleStatus.AVAILABLE
        )

    def test_tenant_base_model_inheritance_and_scoping(self):
        """Verify TenantBaseModel attributes and related_name '%(class)ss'."""
        self.assertTrue(issubclass(Vehicle, TenantBaseModel))
        self.assertTrue(issubclass(Vehicle, TenantOwnedModel))

        # Check fields
        self.assertTrue(hasattr(self.vehicle_a, 'created_at'))
        self.assertTrue(hasattr(self.vehicle_a, 'updated_at'))
        self.assertTrue(hasattr(self.vehicle_a, 'tenant'))

        # Check related_name '%(class)ss' on Tenant
        self.assertTrue(hasattr(self.tenant_a, 'vehicles'))
        self.assertIn(self.vehicle_a, self.tenant_a.vehicles.all())
        self.assertNotIn(self.vehicle_b, self.tenant_a.vehicles.all())

    def test_jwt_token_payload_claims(self):
        """Token payload MUST include: user_id, email, is_platform_admin, tenant_id."""
        login_res = self.client.post('/api/v1/auth/login/', {
            'email': 'alex.morgan@apex.com',
            'password': 'SuperPassword123!'
        })
        self.assertEqual(login_res.status_code, status.HTTP_200_OK)
        access_token_str = login_res.data['access']

        token = AccessToken(access_token_str)
        self.assertEqual(token['user_id'], str(self.user_a.id))
        self.assertEqual(token['email'], 'alex.morgan@apex.com')
        self.assertEqual(token['is_platform_admin'], False)
        self.assertEqual(token['tenant_id'], str(self.tenant_a.id))

    def test_login_endpoint_contract(self):
        """POST /api/v1/auth/login/ returns the exact specification structure."""
        login_res = self.client.post('/api/v1/auth/login/', {
            'email': 'alex.morgan@apex.com',
            'password': 'SuperPassword123!'
        })
        self.assertEqual(login_res.status_code, status.HTTP_200_OK)
        data = login_res.data

        # Top-level keys
        self.assertIn('access', data)
        self.assertIn('refresh', data)
        self.assertIn('mfa_required', data)
        self.assertFalse(data['mfa_required'])
        self.assertIn('user', data)
        self.assertIn('tenants', data)

        # User payload
        user = data['user']
        self.assertEqual(user['id'], str(self.user_a.id))
        self.assertEqual(user['email'], 'alex.morgan@apex.com')
        self.assertEqual(user['first_name'], 'Alex')
        self.assertEqual(user['last_name'], 'Morgan')
        self.assertEqual(user['is_platform_user'], False)
        self.assertIsNone(user['platform_role'])
        self.assertEqual(user['tenant_id'], str(self.tenant_a.id))
        self.assertEqual(user['tenant_role'], 'tenant_admin')
        self.assertIsInstance(user['permissions'], list)
        self.assertFalse(user['mfa_enabled'])
        self.assertEqual(user['status'], 'active')

        # Tenants payload
        tenants = data['tenants']
        self.assertIsInstance(tenants, list)
        self.assertGreaterEqual(len(tenants), 1)
        tenant_entry = tenants[0]
        self.assertEqual(tenant_entry['id'], str(self.tenant_a.id))
        self.assertEqual(tenant_entry['name'], 'Apex Global Logistics')
        self.assertEqual(tenant_entry['slug'], 'apex-global-logistics')
        self.assertEqual(tenant_entry['package_tier'], 'standard')
        self.assertEqual(tenant_entry['status'], 'active')

    def test_refresh_token_endpoints(self):
        """Test both POST /api/v1/auth/refresh/ and POST /api/v1/auth/token/refresh/."""
        # 1. /api/v1/auth/refresh/
        refresh1 = str(RefreshToken.for_user(self.user_a))
        res1 = self.client.post('/api/v1/auth/refresh/', {'refresh': refresh1})
        self.assertEqual(res1.status_code, status.HTTP_200_OK)
        self.assertIn('access', res1.data)

        # 2. /api/v1/auth/token/refresh/ (fresh token since refresh1 was rotated & blacklisted)
        refresh2 = str(RefreshToken.for_user(self.user_a))
        res2 = self.client.post('/api/v1/auth/token/refresh/', {'refresh': refresh2})
        self.assertEqual(res2.status_code, status.HTTP_200_OK)
        self.assertIn('access', res2.data)

    def test_auth_me_endpoint(self):
        """GET /api/v1/auth/me/ returns authenticated user and active tenant structure."""
        self.client.force_authenticate(user=self.user_a)
        res = self.client.get(
            '/api/v1/auth/me/',
            HTTP_X_TENANT_ID=str(self.tenant_a.id)
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.data

        self.assertIn('user', data)
        self.assertIn('tenants', data)
        self.assertEqual(data['user']['email'], 'alex.morgan@apex.com')
        self.assertEqual(data['user']['tenant_id'], str(self.tenant_a.id))
        self.assertEqual(data['user']['tenant_role'], 'tenant_admin')
        self.assertEqual(data['tenants'][0]['name'], 'Apex Global Logistics')

    def test_logout_endpoint(self):
        """POST /api/v1/auth/logout/ accepts refresh token, blacklists it, returns detail message."""
        refresh = RefreshToken.for_user(self.user_a)
        res = self.client.post('/api/v1/auth/logout/', {'refresh': str(refresh)})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['detail'], 'Successfully logged out.')

        # Blacklisted token cannot be used to refresh
        refresh_attempt = self.client.post('/api/v1/auth/refresh/', {'refresh': str(refresh)})
        self.assertEqual(refresh_attempt.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_password_reset_endpoints(self):
        """Test password-reset and password-reset-confirm endpoints."""
        # 1. Reset request
        req_res = self.client.post('/api/v1/auth/password-reset/', {'email': 'alex.morgan@apex.com'})
        self.assertEqual(req_res.status_code, status.HTTP_200_OK)
        self.assertEqual(req_res.data['detail'], 'Password reset link sent.')

        # 2. Reset confirm
        conf_res = self.client.post('/api/v1/auth/password-reset-confirm/', {
            'token': 'mock-reset-token-xyz',
            'new_password': 'NewSecurePassword999!'
        })
        self.assertEqual(conf_res.status_code, status.HTTP_200_OK)
        self.assertIn('detail', conf_res.data)

    def test_mfa_verify_endpoint(self):
        """POST /api/v1/auth/mfa/verify/ accepts email and code, returns full tokens & user."""
        res = self.client.post('/api/v1/auth/mfa/verify/', {
            'email': 'alex.morgan@apex.com',
            'code': '123456'
        })
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.data
        self.assertIn('access', data)
        self.assertIn('refresh', data)
        self.assertIn('user', data)
        self.assertIn('tenants', data)
        self.assertEqual(data['user']['email'], 'alex.morgan@apex.com')

    def test_tenant_header_middleware_scoping_and_cross_tenant_queries(self):
        """
        Verify:
        1. Tenant A user only sees Tenant A vehicles with X-Tenant-ID: <uuid>.
        2. Super Admin without X-Tenant-ID sees all vehicles (cross-tenant).
        3. Super Admin with X-Tenant-ID: 'all' sees all vehicles (cross-tenant).
        4. Super Admin with X-Tenant-ID: <uuid> is scoped to that tenant.
        """
        # 1. User A scoped to Tenant A
        self.client.force_authenticate(user=self.user_a)
        res_a = self.client.get(
            '/api/v1/fleet/vehicles/',
            HTTP_X_TENANT_ID=str(self.tenant_a.id)
        )
        self.assertEqual(res_a.status_code, status.HTTP_200_OK)
        data_a = res_a.data.get('data', res_a.data.get('results', []))
        regs_a = [v['registration_number'] for v in data_a]
        self.assertIn('APEX-101', regs_a)
        self.assertNotIn('BEACON-202', regs_a)

        # 2. Super Admin without X-Tenant-ID -> sees both vehicles
        self.client.force_authenticate(user=self.super_admin)
        res_super_none = self.client.get('/api/v1/fleet/vehicles/')
        self.assertEqual(res_super_none.status_code, status.HTTP_200_OK)
        data_none = res_super_none.data.get('data', res_super_none.data.get('results', []))
        regs_none = [v['registration_number'] for v in data_none]
        self.assertIn('APEX-101', regs_none)
        self.assertIn('BEACON-202', regs_none)

        # 3. Super Admin with X-Tenant-ID: 'all' -> sees both vehicles
        res_super_all = self.client.get(
            '/api/v1/fleet/vehicles/',
            HTTP_X_TENANT_ID='all'
        )
        self.assertEqual(res_super_all.status_code, status.HTTP_200_OK)
        data_all = res_super_all.data.get('data', res_super_all.data.get('results', []))
        regs_all = [v['registration_number'] for v in data_all]
        self.assertIn('APEX-101', regs_all)
        self.assertIn('BEACON-202', regs_all)

        # 4. Super Admin scoped to Tenant B specifically
        res_super_b = self.client.get(
            '/api/v1/fleet/vehicles/',
            HTTP_X_TENANT_ID=str(self.tenant_b.id)
        )
        self.assertEqual(res_super_b.status_code, status.HTTP_200_OK)
        data_b = res_super_b.data.get('data', res_super_b.data.get('results', []))
        regs_b = [v['registration_number'] for v in data_b]
        self.assertNotIn('APEX-101', regs_b)
        self.assertIn('BEACON-202', regs_b)

    def test_perform_create_auto_scopes_tenant(self):
        """Creating a vehicle automatically sets tenant=request.tenant."""
        self.client.force_authenticate(user=self.user_a)
        create_res = self.client.post(
            '/api/v1/fleet/vehicles/',
            {
                'registration_number': 'AUTO-SCOPE-01',
                'make': 'MAN',
                'model': 'TGX',
                'vertical': 'freight_logistics',
                'type': 'heavy_truck',
            },
            HTTP_X_TENANT_ID=str(self.tenant_a.id)
        )
        self.assertEqual(create_res.status_code, status.HTTP_201_CREATED)
        vehicle = Vehicle.objects.get(registration_number='AUTO-SCOPE-01')
        self.assertEqual(vehicle.tenant, self.tenant_a)
