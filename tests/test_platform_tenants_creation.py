from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model
from apps.tenants.models import Tenant, TenantStatus
from apps.subscriptions.models import Package, PackageTier

User = get_user_model()


class PlatformTenantsCreationTests(APITestCase):
    def setUp(self):
        Package.objects.get_or_create(
            code=PackageTier.STANDARD,
            defaults={'name': 'Standard', 'price_monthly': 399.00, 'price_yearly': 3990.00}
        )
        self.super_admin = User.objects.create_superuser(
            email="platform.admin.tenant.test@omnicore.io",
            password="SuperPassword123!",
            first_name="Platform",
            last_name="Admin"
        )
        self.client.force_authenticate(user=self.super_admin)

    def test_post_platform_tenants_creates_unique_tenant_id_and_slug(self):
        """
        Verify that POST /api/v1/platform/tenants/ automatically generates
        a unique tenant_id and slug without violating unique constraints.
        """
        # 1. First tenant creation
        res1 = self.client.post('/api/v1/platform/tenants/', {
            'company_name': 'Alpha Cargo Logistics',
            'email': 'contact@alphacargo.com',
            'phone': '+1234567890',
        }, format='json')
        self.assertEqual(res1.status_code, status.HTTP_201_CREATED, res1.data)
        data1 = res1.data.get('data', res1.data)
        self.assertTrue(data1['tenant_id'].startswith('OCT-'))
        self.assertEqual(data1['slug'], 'alpha-cargo-logistics')
        self.assertEqual(data1['status'], TenantStatus.ACTIVE)

        # 2. Second tenant creation (must succeed without UniqueViolation on tenant_id or slug)
        res2 = self.client.post('/api/v1/platform/tenants/', {
            'company_name': 'Beta Freight Solutions',
            'email': 'contact@betafreight.com',
            'phone': '+1987654321',
        }, format='json')
        self.assertEqual(res2.status_code, status.HTTP_201_CREATED, res2.data)
        data2 = res2.data.get('data', res2.data)
        self.assertTrue(data2['tenant_id'].startswith('OCT-'))
        self.assertNotEqual(data1['tenant_id'], data2['tenant_id'])
        self.assertEqual(data2['slug'], 'beta-freight-solutions')

        # 3. Third tenant creation with same company_name -> unique slug and unique tenant_id
        res3 = self.client.post('/api/v1/platform/tenants/', {
            'company_name': 'Alpha Cargo Logistics',
            'email': 'contact2@alphacargo.com',
        }, format='json')
        self.assertEqual(res3.status_code, status.HTTP_201_CREATED, res3.data)
        data3 = res3.data.get('data', res3.data)
        self.assertTrue(data3['tenant_id'].startswith('OCT-'))
        self.assertNotEqual(data1['tenant_id'], data3['tenant_id'])
        self.assertEqual(data3['slug'], 'alpha-cargo-logistics-1')

    def test_direct_model_create_auto_generates_tenant_id_and_slug(self):
        """
        Direct model creation without serializer also auto-populates tenant_id and slug.
        """
        t = Tenant.objects.create(company_name="Gamma Express", email="gamma@express.com")
        self.assertTrue(t.tenant_id.startswith('OCT-'))
        self.assertEqual(t.slug, 'gamma-express')
