import uuid
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from apps.core.models import TenantOwnedModel


class TransactionType(models.TextChoices):
    RECEIVE = 'RECEIVE', _('Goods Receipt / Restock')
    ISSUE = 'ISSUE', _('Issue to Maintenance / Repair')
    RETURN = 'RETURN', _('Return to Stock')
    ADJUSTMENT = 'ADJUSTMENT', _('Physical Inventory Adjustment')
    TRANSFER = 'TRANSFER', _('Inter-Warehouse Transfer')


class PurchaseOrderStatus(models.TextChoices):
    DRAFT = 'DRAFT', _('Draft')
    ISSUED = 'ISSUED', _('Issued to Supplier')
    PARTIALLY_RECEIVED = 'PARTIALLY_RECEIVED', _('Partially Received')
    RECEIVED = 'RECEIVED', _('Fully Received')
    CANCELLED = 'CANCELLED', _('Cancelled')


class Warehouse(TenantOwnedModel):
    name = models.CharField(max_length=150)
    code = models.CharField(max_length=50, db_index=True)
    address = models.TextField(blank=True)
    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='managed_warehouses'
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('tenant', 'code')

    def __str__(self):
        return f"{self.name} ({self.code})"


class Supplier(TenantOwnedModel):
    name = models.CharField(max_length=200, db_index=True)
    code = models.CharField(max_length=50)
    contact_person = models.CharField(max_length=150, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    address = models.TextField(blank=True)
    payment_terms_days = models.PositiveIntegerField(default=30)

    class Meta:
        unique_together = ('tenant', 'code')

    def __str__(self):
        return self.name


class SparePart(TenantOwnedModel):
    """
    Inventory SKU for maintenance consumables and truck components.
    """
    part_number = models.CharField(max_length=100, db_index=True)
    name = models.CharField(max_length=200)
    category = models.CharField(max_length=100, default='GENERAL')
    unit = models.CharField(max_length=20, default='PCS')  # PCS, LTR, KG, SET
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    current_stock = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, db_index=True)
    minimum_stock = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    reorder_level = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)

    class Meta:
        ordering = ['-created_at']
        unique_together = ('tenant', 'part_number')
        indexes = [
            models.Index(fields=['tenant', 'current_stock']),
        ]

    def __str__(self):
        return f"{self.part_number} - {self.name} (Stock: {self.current_stock})"

    @property
    def is_low_stock(self):
        return self.current_stock <= self.reorder_level


class PurchaseOrder(TenantOwnedModel):
    po_number = models.CharField(max_length=100, db_index=True)
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name='purchase_orders')
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name='purchase_orders')
    order_date = models.DateField(db_index=True)
    expected_date = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=30,
        choices=PurchaseOrderStatus.choices,
        default=PurchaseOrderStatus.DRAFT,
        db_index=True
    )
    total_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0.00)
    notes = models.TextField(blank=True)

    class Meta:
        unique_together = ('tenant', 'po_number')

    def __str__(self):
        return f"PO {self.po_number} -> {self.supplier.name}"


class PurchaseOrderItem(TenantOwnedModel):
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name='items')
    spare_part = models.ForeignKey(SparePart, on_delete=models.CASCADE, related_name='po_items')
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    total_price = models.DecimalField(max_digits=12, decimal_places=2)

    def save(self, *args, **kwargs):
        self.total_price = self.quantity * self.unit_price
        super().save(*args, **kwargs)


class GoodsReceipt(TenantOwnedModel):
    grn_number = models.CharField(max_length=100, db_index=True)
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name='goods_receipts')
    receipt_date = models.DateTimeField(auto_now_add=True)
    received_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    notes = models.TextField(blank=True)

    class Meta:
        unique_together = ('tenant', 'grn_number')


class InventoryTransaction(TenantOwnedModel):
    """
    Immutable ledger of all stock balance movements.
    Stock balance on SparePart MUST ONLY be adjusted via this model through InventoryService.
    """
    transaction_type = models.CharField(max_length=30, choices=TransactionType.choices, db_index=True)
    spare_part = models.ForeignKey(SparePart, on_delete=models.CASCADE, related_name='transactions')
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name='inventory_movements')
    quantity = models.DecimalField(max_digits=12, decimal_places=2, help_text="Positive for addition, negative for deduction")
    previous_stock = models.DecimalField(max_digits=12, decimal_places=2)
    new_stock = models.DecimalField(max_digits=12, decimal_places=2)
    reference_id = models.CharField(max_length=100, blank=True)
    reference_type = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['tenant', 'spare_part', 'created_at']),
            models.Index(fields=['tenant', 'transaction_type']),
        ]

    def __str__(self):
        return f"{self.transaction_type} {self.quantity} on {self.spare_part.part_number} (New: {self.new_stock})"


class WarehouseDeliveryDirection(models.TextChoices):
    INCOMING = 'INCOMING', _('Incoming Shipment to Warehouse')
    OUTGOING = 'OUTGOING', _('Outgoing Dispatch from Warehouse')
    EXCHANGE = 'EXCHANGE', _('Warehouse Inter-Facility Exchange')


class WarehouseDeliveryStatus(models.TextChoices):
    PENDING = 'PENDING', _('Pending Arrival / Schedule')
    RECEIVED = 'RECEIVED', _('Received at Warehouse Bay')
    STAGED = 'STAGED', _('Staged for Inspection / Sort')
    DISPATCHED = 'DISPATCHED', _('Dispatched')
    COMPLETED = 'COMPLETED', _('Completed')
    CANCELLED = 'CANCELLED', _('Cancelled')


class CrossDockStatus(models.TextChoices):
    INBOUND_RECEIVED = 'INBOUND_RECEIVED', _('Inbound Cargo Received')
    SORTING = 'SORTING', _('Sortation in Cross-Dock Bay')
    CONSOLIDATED = 'CONSOLIDATED', _('Consolidated to Outbound Unit')
    OUTBOUND_DISPATCHED = 'OUTBOUND_DISPATCHED', _('Dispatched to Destination')
    COMPLETED = 'COMPLETED', _('Cross-Dock Transfer Completed')


class ConsolidationStatus(models.TextChoices):
    OPEN = 'OPEN', _('Open for Inbound Manifests')
    SEALED = 'SEALED', _('Sealed for Transit')
    DISPATCHED = 'DISPATCHED', _('Dispatched')
    DELIVERED = 'DELIVERED', _('Delivered and Broken Down')


class WarehouseDelivery(TenantOwnedModel):
    """
    Invoice-wise and operational inbound/outbound warehouse delivery movement.
    """
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name='warehouse_deliveries')
    delivery_number = models.CharField(max_length=50, db_index=True)
    direction = models.CharField(max_length=20, choices=WarehouseDeliveryDirection.choices, default=WarehouseDeliveryDirection.INCOMING)
    invoice = models.ForeignKey('finance.Invoice', null=True, blank=True, on_delete=models.SET_NULL, related_name='warehouse_deliveries')
    status = models.CharField(max_length=30, choices=WarehouseDeliveryStatus.choices, default=WarehouseDeliveryStatus.PENDING, db_index=True)
    expected_time = models.DateTimeField(null=True, blank=True)
    actual_time = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = ('tenant', 'delivery_number')
        indexes = [
            models.Index(fields=['tenant', 'warehouse', 'status']),
            models.Index(fields=['tenant', 'delivery_number']),
        ]

    def __str__(self):
        return f"WH-DEL {self.delivery_number} ({self.direction}) - {self.status}"


class CrossDockOperation(TenantOwnedModel):
    """
    Direct inbound-to-outbound sort and transfer bypassing long-term storage.
    Workflow: Inbound -> Receive -> Sort -> Consolidate -> Outbound -> Dispatch.
    """
    cross_dock_number = models.CharField(max_length=50, db_index=True)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name='cross_dock_operations')
    source_location = models.CharField(max_length=255)
    destination_location = models.CharField(max_length=255)
    inbound_carrier = models.CharField(max_length=150, blank=True)
    outbound_carrier = models.CharField(max_length=150, blank=True)
    operator = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    status = models.CharField(max_length=30, choices=CrossDockStatus.choices, default=CrossDockStatus.INBOUND_RECEIVED, db_index=True)
    inbound_time = models.DateTimeField(auto_now_add=True)
    outbound_time = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-inbound_time']
        unique_together = ('tenant', 'cross_dock_number')
        indexes = [
            models.Index(fields=['tenant', 'status']),
            models.Index(fields=['tenant', 'warehouse']),
        ]

    def __str__(self):
        return f"CrossDock {self.cross_dock_number} ({self.source_location} -> {self.destination_location}) [{self.status}]"


class CrossDockShipment(TenantOwnedModel):
    """
    Individual courier shipment or freight unit assigned to a cross-dock operation.
    """
    cross_dock = models.ForeignKey(CrossDockOperation, on_delete=models.CASCADE, related_name='shipments')
    shipment = models.ForeignKey('courier.Shipment', null=True, blank=True, on_delete=models.SET_NULL, related_name='cross_dock_movements')
    reference_id = models.CharField(max_length=100, db_index=True)
    parcel_count = models.PositiveIntegerField(default=1)
    weight_kg = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    status = models.CharField(max_length=50, default='TRANSFERRED')


class ConsolidationGroup(TenantOwnedModel):
    """
    Multi-day and multi-invoice shipment consolidation container for hub/destination distribution.
    """
    group_code = models.CharField(max_length=50, db_index=True)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name='consolidation_groups')
    hub = models.ForeignKey('courier.Hub', null=True, blank=True, on_delete=models.SET_NULL, related_name='consolidations')
    destination_zone = models.CharField(max_length=150, db_index=True)
    date_from = models.DateField()
    date_to = models.DateField()
    total_parcels = models.PositiveIntegerField(default=0)
    total_weight_kg = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    status = models.CharField(max_length=30, choices=ConsolidationStatus.choices, default=ConsolidationStatus.OPEN, db_index=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-date_to']
        unique_together = ('tenant', 'group_code')
        indexes = [
            models.Index(fields=['tenant', 'status']),
            models.Index(fields=['tenant', 'destination_zone']),
        ]

    def __str__(self):
        return f"Consolidation {self.group_code} -> {self.destination_zone} [{self.status}]"


class ConsolidatedShipmentItem(TenantOwnedModel):
    """
    Shipment or invoice package item bundled within a consolidation group.
    """
    group = models.ForeignKey(ConsolidationGroup, on_delete=models.CASCADE, related_name='items')
    shipment = models.ForeignKey('courier.Shipment', null=True, blank=True, on_delete=models.SET_NULL, related_name='consolidation_items')
    invoice_reference = models.CharField(max_length=100, blank=True)
    parcel_count = models.PositiveIntegerField(default=1)
    weight_kg = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    added_at = models.DateTimeField(auto_now_add=True)

