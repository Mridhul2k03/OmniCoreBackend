from rest_framework.test import APITestCase
from rest_framework import status
from apps.tenants.services import TenantProvisioningService
from apps.subscriptions.models import Feature, Addon
from apps.subscriptions.services import sync_tenant_features


class FeatureEntitlementTests(APITestCase):
    def setUp(self):
        # Create 'warehouse' and 'contracts' feature records
        self.feat_warehouse, _ = Feature.objects.get_or_create(
            code='warehouse',
            defaults={'name': 'Warehouse & Spare Parts', 'category': 'warehouse'}
        )
        self.feat_contracts, _ = Feature.objects.get_or_create(
            code='contracts',
            defaults={'name': 'Contract & Tender Management', 'category': 'contracts'}
        )

        # Create addon for warehouse
        self.addon_warehouse, _ = Addon.objects.get_or_create(
            code='warehouse_addon',
            defaults={'name': 'Warehouse Pack', 'monthly_price': 49.00}
        )
        self.addon_warehouse.features.add(self.feat_warehouse)

        # Provision Tenant on BASIC (which lacks warehouse and contracts)
        self.tenant_data = TenantProvisioningService.provision(
            company_name="Basic Shipper Co",
            admin_email="admin@basic.com",
            admin_password="Password123!",
            package_code="BASIC"
        )
        self.tenant = self.tenant_data['tenant']
        self.user = self.tenant_data['admin_user']

    def test_unentitled_feature_blocked(self):
        """
        A tenant without warehouse entitlement must receive 403 FEATURE_NOT_ENTITLED
        when attempting to access warehouse endpoints.
        """
        self.client.force_authenticate(user=self.user)
        response = self.client.get(
            '/api/v1/warehouse/parts/',
            HTTP_X_TENANT_ID=self.tenant.tenant_id
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data['error']['code'], 'FEATURE_NOT_ENTITLED')

    def test_feature_enabled_after_addon_attachment(self):
        """
        When the addon is attached to the subscription, the warehouse endpoint becomes accessible.
        """
        # Attach addon and sync features
        sub = self.tenant.subscription
        sub.addons.add(self.addon_warehouse)
        sync_tenant_features(self.tenant)

        self.client.force_authenticate(user=self.user)
        response = self.client.get(
            '/api/v1/warehouse/parts/',
            HTTP_X_TENANT_ID=self.tenant.tenant_id
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
