from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model
from apps.tenants.services import TenantProvisioningService
from apps.tenants.models import Tenant, TenantUser

User = get_user_model()


class ProvisioningAndAuthTests(APITestCase):
    def test_tenant_provisioning_workflow(self):
        result = TenantProvisioningService.provision(
            company_name="Apex Logistics Inc",
            admin_email="ceo@apexlogistics.com",
            admin_password="SuperSecretPassword123!",
            admin_first_name="John",
            admin_last_name="Doe",
            package_code="CORPORATE"
        )

        tenant = result['tenant']
        admin_user = result['admin_user']

        # Assertions on generated entity
        self.assertTrue(tenant.tenant_id.startswith("OCT-"))
        self.assertEqual(tenant.status, "ACTIVE")
        self.assertIsNotNone(tenant.activated_at)
        self.assertEqual(tenant.slug, "apex-logistics-inc")

        # Verify TenantUser membership
        membership = TenantUser.objects.filter(tenant=tenant, user=admin_user).first()
        self.assertIsNotNone(membership)
        self.assertEqual(membership.role.code, "TENANT_ADMIN")
        self.assertTrue(membership.is_primary)
        self.assertTrue(membership.is_active)

    def test_jwt_login_and_auth_me(self):
        # 1. Provision
        result = TenantProvisioningService.provision(
            company_name="FastFreight Systems",
            admin_email="dispatch@fastfreight.com",
            admin_password="Password123!",
            package_code="CORPORATE"
        )
        tenant = result['tenant']

        # 2. Login
        login_res = self.client.post(
            '/api/v1/auth/login/',
            {
                'email': 'dispatch@fastfreight.com',
                'password': 'Password123!'
            }
        )
        self.assertEqual(login_res.status_code, status.HTTP_200_OK)
        payload = login_res.data.get('data', login_res.data)
        self.assertIn('access', payload)
        self.assertIn('refresh', payload)
        self.assertIn('tenants', payload)
        self.assertEqual(payload['tenants'][0]['tenant_id'], tenant.tenant_id)

        access_token = payload['access']

        # 3. Call GET /api/v1/auth/me/
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        me_res = self.client.get(
            '/api/v1/auth/me/',
            HTTP_X_TENANT_ID=tenant.tenant_id
        )
        self.assertEqual(me_res.status_code, status.HTTP_200_OK)
        me_payload = me_res.data.get('data', me_res.data)
        self.assertEqual(me_payload['user']['email'], 'dispatch@fastfreight.com')
        self.assertEqual(me_payload['active_tenant']['tenant_id'], tenant.tenant_id)
        self.assertEqual(me_payload['role']['code'], 'TENANT_ADMIN')

        # 4. Logout (Blacklist token)
        logout_res = self.client.post(
            '/api/v1/auth/logout/',
            {'refresh': payload['refresh']}
        )
        self.assertEqual(logout_res.status_code, status.HTTP_200_OK)
