from decimal import Decimal
from rest_framework.test import APITestCase
from apps.tenants.services import TenantProvisioningService
from apps.warehouse.models import Warehouse, SparePart, TransactionType
from apps.warehouse.services import InventoryService
from apps.core.exceptions import BusinessValidationError


class InventoryServiceTests(APITestCase):
    def setUp(self):
        self.tenant_data = TenantProvisioningService.provision(
            company_name="Precision Fleet Logistics",
            admin_email="parts@precision.com",
            admin_password="Password123!",
            package_code="CORPORATE"
        )
        self.tenant = self.tenant_data['tenant']
        self.user = self.tenant_data['admin_user']

        self.warehouse = Warehouse.objects.create(
            tenant=self.tenant,
            name="Central Hub Depot",
            code="HUB-01"
        )
        self.part = SparePart.objects.create(
            tenant=self.tenant,
            part_number="BRK-PAD-001",
            name="Ceramic Brake Pad Set",
            unit_cost=Decimal("75.00"),
            current_stock=Decimal("10.00"),
            minimum_stock=Decimal("5.00"),
            reorder_level=Decimal("8.00")
        )

    def test_stock_issue_and_balance_update(self):
        tx = InventoryService.record_stock_movement(
            tenant=self.tenant,
            spare_part_id=self.part.id,
            warehouse_id=self.warehouse.id,
            transaction_type=TransactionType.ISSUE,
            quantity=Decimal("4.00"),
            actor=self.user
        )
        self.part.refresh_from_db()
        self.assertEqual(self.part.current_stock, Decimal("6.00"))
        self.assertEqual(tx.previous_stock, Decimal("10.00"))
        self.assertEqual(tx.new_stock, Decimal("6.00"))
        self.assertEqual(tx.quantity, Decimal("-4.00"))

    def test_stock_receive(self):
        tx = InventoryService.record_stock_movement(
            tenant=self.tenant,
            spare_part_id=self.part.id,
            warehouse_id=self.warehouse.id,
            transaction_type=TransactionType.RECEIVE,
            quantity=Decimal("20.00"),
            actor=self.user
        )
        self.part.refresh_from_db()
        self.assertEqual(self.part.current_stock, Decimal("30.00"))
        self.assertEqual(tx.new_stock, Decimal("30.00"))

    def test_negative_inventory_prevented(self):
        """
        Attempting to issue more items than available in stock MUST fail.
        """
        with self.assertRaises(BusinessValidationError):
            InventoryService.record_stock_movement(
                tenant=self.tenant,
                spare_part_id=self.part.id,
                warehouse_id=self.warehouse.id,
                transaction_type=TransactionType.ISSUE,
                quantity=Decimal("50.00"),  # Only 10 available
                actor=self.user
            )

        self.part.refresh_from_db()
        # Ensure stock remained unchanged
        self.assertEqual(self.part.current_stock, Decimal("10.00"))
