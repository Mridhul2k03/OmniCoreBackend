from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model
from apps.tenants.models import Tenant, TenantUser
from apps.subscriptions.models import Package, Subscription, PackageTier, BillingCycle

User = get_user_model()


class RegistrationAndActivationTests(APITestCase):
    def setUp(self):
        # Ensure packages exist
        Package.objects.get_or_create(
            code=PackageTier.BASIC,
            defaults={'name': 'Basic', 'price_monthly': 149.00, 'price_yearly': 1490.00}
        )
        Package.objects.get_or_create(
            code=PackageTier.CORPORATE,
            defaults={'name': 'Corporate', 'price_monthly': 899.00, 'price_yearly': 8990.00}
        )
        Package.objects.get_or_create(
            code=PackageTier.ENTERPRISE,
            defaults={'name': 'Enterprise', 'price_monthly': 1899.00, 'price_yearly': 18990.00}
        )

    def test_tenant_registration_flow(self):
        """Test step 1 registration for a new tenant and admin user."""
        res = self.client.post(
            '/api/v1/auth/register/',
            {
                'company_name': 'Horizon Health Logistics',
                'email': 'admin@horizonhealth.com',
                'password': 'SecurePassword123!',
                'first_name': 'Sarah',
                'last_name': 'Connor',
                'phone': '+1-555-0100',
                'is_super_admin': False,
                'package_tier': 'corporate'
            },
            format='json'
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        data = res.data.get('data', res.data)
        self.assertIn('access', data)
        self.assertIn('refresh', data)
        self.assertEqual(data['user']['email'], 'admin@horizonhealth.com')
        self.assertIsNotNone(data.get('tenant'))
        self.assertEqual(data['tenant']['name'], 'Horizon Health Logistics')
        self.assertEqual(data['tenant']['package_tier'], 'corporate')

        # Test signup alias route with different email
        alias_res = self.client.post(
            '/api/v1/auth/signup/',
            {
                'company_name': 'Nova Transport',
                'email': 'admin@novatransport.com',
                'password': 'SecurePassword123!',
                'package_tier': 'basic'
            },
            format='json'
        )
        self.assertEqual(alias_res.status_code, status.HTTP_201_CREATED)

    def test_registration_duplicate_email(self):
        """Test that registering duplicate email fails with 400."""
        payload = {
            'company_name': 'First Co',
            'email': 'duplicate@example.com',
            'password': 'SecurePassword123!',
            'package_tier': 'basic'
        }
        res1 = self.client.post('/api/v1/auth/register/', payload, format='json')
        self.assertEqual(res1.status_code, status.HTTP_201_CREATED)

        res2 = self.client.post('/api/v1/auth/register/', payload, format='json')
        self.assertEqual(res2.status_code, status.HTTP_400_BAD_REQUEST)

    def test_super_admin_registration(self):
        """Test registration of a platform super admin (no tenant created)."""
        res = self.client.post(
            '/api/v1/auth/register/',
            {
                'company_name': 'Platform Ops',
                'email': 'superadmin@omnicore.io',
                'password': 'SuperPassword123!',
                'is_super_admin': True
            },
            format='json'
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        data = res.data.get('data', res.data)
        self.assertTrue(data['user']['is_platform_admin'])
        self.assertIsNone(data.get('tenant'))

    def test_plan_activation_flow(self):
        """Test step 2 plan activation."""
        # 1. Register tenant
        reg_res = self.client.post(
            '/api/v1/auth/register/',
            {
                'company_name': 'Pulse Medical Transit',
                'email': 'director@pulsemed.com',
                'password': 'SecurePassword123!',
                'package_tier': 'basic'
            },
            format='json'
        )
        self.assertEqual(reg_res.status_code, status.HTTP_201_CREATED)
        reg_data = reg_res.data.get('data', reg_res.data)
        token = reg_data['access']
        tenant_id = reg_data['tenant']['tenant_id']

        # 2. Activate Plan (Upgrade to corporate)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        act_res = self.client.post(
            '/api/v1/auth/activate-plan/',
            {
                'tenant_id': tenant_id,
                'package_tier': 'corporate',
                'billing_cycle': 'monthly'
            },
            format='json'
        )
        self.assertEqual(act_res.status_code, status.HTTP_200_OK)
        act_data = act_res.data.get('data', act_res.data)
        self.assertEqual(act_data['package_tier'], 'corporate')
        self.assertEqual(act_data['billing_cycle'], 'monthly')
        self.assertEqual(act_data['status'], 'active')
        self.assertEqual(act_data['mrr'], 899.0)

    def test_platform_tenant_upgrade(self):
        """Test platform admin upgrading a tenant's plan."""
        # 1. Register a tenant
        reg_res = self.client.post(
            '/api/v1/auth/register/',
            {
                'company_name': 'CareRoute Systems',
                'email': 'admin@careroute.com',
                'password': 'SecurePassword123!',
                'package_tier': 'basic'
            },
            format='json'
        )
        tenant_id = reg_res.data.get('data', reg_res.data)['tenant']['tenant_id']

        # 2. Create and authenticate platform admin
        admin_user = User.objects.create_superuser(
            email='root@platform.io',
            password='RootPassword123!',
            is_platform_admin=True
        )
        self.client.force_authenticate(user=admin_user)

        # 3. Upgrade tenant plan
        upg_res = self.client.post(
            f'/api/v1/platform/tenants/{tenant_id}/upgrade/',
            {
                'package_tier': 'enterprise',
                'billing_cycle': 'annually'
            },
            format='json'
        )
        self.assertEqual(upg_res.status_code, status.HTTP_200_OK)
        upg_data = upg_res.data.get('data', upg_res.data)
        self.assertEqual(upg_data['tenant_id'], tenant_id)
        self.assertEqual(upg_data['package_tier'], 'enterprise')
        self.assertEqual(upg_data['mrr'], 1899.0)
