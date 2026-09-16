from rest_framework import serializers
from apps.warehouse.models import (
    Warehouse,
    Supplier,
    SparePart,
    PurchaseOrder,
    PurchaseOrderItem,
    InventoryTransaction,
)


class WarehouseSerializer(serializers.ModelSerializer):
    manager_name = serializers.CharField(source='manager.full_name', read_only=True)

    class Meta:
        model = Warehouse
        fields = ['id', 'name', 'code', 'address', 'manager', 'manager_name', 'is_active', 'created_at']
        read_only_fields = ['id', 'created_at']


class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = ['id', 'name', 'code', 'contact_person', 'email', 'phone', 'address', 'payment_terms_days', 'created_at']
        read_only_fields = ['id', 'created_at']


class SparePartSerializer(serializers.ModelSerializer):
    is_low_stock = serializers.BooleanField(read_only=True)

    class Meta:
        model = SparePart
        fields = [
            'id', 'part_number', 'name', 'category', 'unit', 'unit_cost',
            'current_stock', 'minimum_stock', 'reorder_level', 'is_low_stock',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'current_stock', 'created_at', 'updated_at']


class PurchaseOrderItemSerializer(serializers.ModelSerializer):
    part_name = serializers.CharField(source='spare_part.name', read_only=True)

    class Meta:
        model = PurchaseOrderItem
        fields = ['id', 'purchase_order', 'spare_part', 'part_name', 'quantity', 'unit_price', 'total_price']
        read_only_fields = ['id', 'total_price']


class PurchaseOrderSerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)
    items = PurchaseOrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = PurchaseOrder
        fields = [
            'id', 'po_number', 'supplier', 'supplier_name', 'warehouse',
            'warehouse_name', 'order_date', 'expected_date', 'status',
            'total_amount', 'notes', 'items', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class InventoryTransactionSerializer(serializers.ModelSerializer):
    part_name = serializers.CharField(source='spare_part.name', read_only=True)
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)

    class Meta:
        model = InventoryTransaction
        fields = [
            'id', 'transaction_type', 'spare_part', 'part_name', 'warehouse',
            'warehouse_name', 'quantity', 'previous_stock', 'new_stock',
            'reference_id', 'reference_type', 'notes', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class WarehouseDeliverySerializer(serializers.ModelSerializer):
    warehouse_name = serializers.ReadOnlyField(source='warehouse.name')

    class Meta:
        from apps.warehouse.models import WarehouseDelivery
        model = WarehouseDelivery
        fields = [
            'id', 'warehouse', 'warehouse_name', 'delivery_number', 'direction',
            'invoice', 'status', 'expected_time', 'actual_time', 'notes', 'created_at'
        ]
        read_only_fields = ['id', 'warehouse_name', 'created_at']


class CrossDockShipmentSerializer(serializers.ModelSerializer):
    class Meta:
        from apps.warehouse.models import CrossDockShipment
        model = CrossDockShipment
        fields = ['id', 'cross_dock', 'shipment', 'reference_id', 'parcel_count', 'weight_kg', 'status']
        read_only_fields = ['id']


class CrossDockOperationSerializer(serializers.ModelSerializer):
    shipments = CrossDockShipmentSerializer(many=True, read_only=True)
    warehouse_name = serializers.ReadOnlyField(source='warehouse.name')

    class Meta:
        from apps.warehouse.models import CrossDockOperation
        model = CrossDockOperation
        fields = [
            'id', 'cross_dock_number', 'warehouse', 'warehouse_name', 'source_location',
            'destination_location', 'inbound_carrier', 'outbound_carrier',
            'operator', 'status', 'inbound_time', 'outbound_time', 'notes', 'shipments'
        ]
        read_only_fields = ['id', 'warehouse_name', 'inbound_time']


class ConsolidatedShipmentItemSerializer(serializers.ModelSerializer):
    class Meta:
        from apps.warehouse.models import ConsolidatedShipmentItem
        model = ConsolidatedShipmentItem
        fields = ['id', 'group', 'shipment', 'invoice_reference', 'parcel_count', 'weight_kg', 'added_at']
        read_only_fields = ['id', 'added_at']


class ConsolidationGroupSerializer(serializers.ModelSerializer):
    items = ConsolidatedShipmentItemSerializer(many=True, read_only=True)
    warehouse_name = serializers.ReadOnlyField(source='warehouse.name')

    class Meta:
        from apps.warehouse.models import ConsolidationGroup
        model = ConsolidationGroup
        fields = [
            'id', 'group_code', 'warehouse', 'warehouse_name', 'hub', 'destination_zone',
            'date_from', 'date_to', 'total_parcels', 'total_weight_kg',
            'status', 'notes', 'items', 'created_at'
        ]
        read_only_fields = ['id', 'warehouse_name', 'total_parcels', 'total_weight_kg', 'created_at']

