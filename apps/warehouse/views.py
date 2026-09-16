from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from apps.core.viewsets import TenantModelViewSet
from apps.warehouse.models import (
    Warehouse,
    Supplier,
    SparePart,
    PurchaseOrder,
    InventoryTransaction,
)
from apps.warehouse.serializers import (
    WarehouseSerializer,
    SupplierSerializer,
    SparePartSerializer,
    PurchaseOrderSerializer,
    InventoryTransactionSerializer,
)
from apps.warehouse.services import InventoryService
from apps.core.exceptions import BusinessValidationError


class WarehouseViewSet(TenantModelViewSet):
    queryset = Warehouse.objects.all().select_related('manager')
    serializer_class = WarehouseSerializer
    required_feature = 'warehouse'
    required_permission = 'warehouse.view'
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['is_active']
    search_fields = ['name', 'code']


class SupplierViewSet(TenantModelViewSet):
    queryset = Supplier.objects.all()
    serializer_class = SupplierSerializer
    required_feature = 'warehouse'
    required_permission = 'warehouse.view'
    filter_backends = [DjangoFilterBackend, SearchFilter]
    search_fields = ['name', 'code', 'contact_person', 'email']


class SparePartViewSet(TenantModelViewSet):
    queryset = SparePart.objects.all()
    serializer_class = SparePartSerializer
    required_feature = 'warehouse'
    required_permission = 'warehouse.view'
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['category']
    search_fields = ['part_number', 'name']
    ordering_fields = ['current_stock', 'name']

    @action(detail=True, methods=['post'])
    def adjust_stock(self, request, pk=None):
        part = self.get_object()
        warehouse_id = request.data.get('warehouse_id')
        transaction_type = request.data.get('transaction_type')
        quantity = request.data.get('quantity')
        notes = request.data.get('notes', '')

        if not warehouse_id or not transaction_type or quantity is None:
            raise BusinessValidationError("Fields 'warehouse_id', 'transaction_type', and 'quantity' are required.")

        tx = InventoryService.record_stock_movement(
            tenant=request.tenant,
            spare_part_id=part.id,
            warehouse_id=warehouse_id,
            transaction_type=transaction_type,
            quantity=quantity,
            notes=notes,
            actor=request.user
        )

        return Response({
            'message': 'Stock movement recorded successfully.',
            'transaction_id': str(tx.id),
            'previous_stock': str(tx.previous_stock),
            'new_stock': str(tx.new_stock)
        })


class PurchaseOrderViewSet(TenantModelViewSet):
    queryset = PurchaseOrder.objects.all().select_related('supplier', 'warehouse').prefetch_related('items__spare_part')
    serializer_class = PurchaseOrderSerializer
    required_feature = 'warehouse'
    required_permission = 'warehouse.view'
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'supplier', 'warehouse']
    search_fields = ['po_number']
    ordering_fields = ['order_date', 'total_amount']


class InventoryTransactionViewSet(TenantModelViewSet):
    queryset = InventoryTransaction.objects.all().select_related('spare_part', 'warehouse')
    serializer_class = InventoryTransactionSerializer
    required_feature = 'warehouse'
    required_permission = 'warehouse.view'
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['transaction_type', 'spare_part', 'warehouse']
    ordering_fields = ['created_at']
    http_method_names = ['get', 'head', 'options']


class WarehouseDeliveryViewSet(TenantModelViewSet):
    from apps.warehouse.models import WarehouseDelivery
    from apps.warehouse.serializers import WarehouseDeliverySerializer
    queryset = WarehouseDelivery.objects.all().select_related('warehouse', 'invoice')
    serializer_class = WarehouseDeliverySerializer
    required_feature = 'warehouse'
    required_permission = 'warehouse.view'
    filterset_fields = ['status', 'direction', 'warehouse']
    search_fields = ['delivery_number']


class CrossDockOperationViewSet(TenantModelViewSet):
    from apps.warehouse.models import CrossDockOperation
    from apps.warehouse.serializers import CrossDockOperationSerializer
    queryset = CrossDockOperation.objects.all().select_related('warehouse', 'operator').prefetch_related('shipments')
    serializer_class = CrossDockOperationSerializer
    required_feature = 'warehouse'
    required_permission = 'warehouse.view'
    filterset_fields = ['status', 'warehouse']
    search_fields = ['cross_dock_number', 'source_location', 'destination_location']

    @action(detail=True, methods=['post'], url_path='advance-status')
    def advance_status(self, request, pk=None):
        cd = self.get_object()
        new_status = request.data.get('status')
        outbound_carrier = request.data.get('outbound_carrier', '')
        notes = request.data.get('notes', '')

        from apps.warehouse.services import CrossDockService
        cd = CrossDockService.advance_status(
            cross_dock=cd,
            new_status=new_status,
            outbound_carrier=outbound_carrier,
            actor=request.user,
            notes=notes
        )
        from apps.warehouse.serializers import CrossDockOperationSerializer
        return Response(CrossDockOperationSerializer(cd).data)


class ConsolidationGroupViewSet(TenantModelViewSet):
    from apps.warehouse.models import ConsolidationGroup
    from apps.warehouse.serializers import ConsolidationGroupSerializer
    queryset = ConsolidationGroup.objects.all().select_related('warehouse', 'hub').prefetch_related('items')
    serializer_class = ConsolidationGroupSerializer
    required_feature = 'warehouse'
    required_permission = 'warehouse.view'
    filterset_fields = ['status', 'warehouse', 'destination_zone']
    search_fields = ['group_code', 'destination_zone']

    @action(detail=True, methods=['post'], url_path='add-item')
    def add_item(self, request, pk=None):
        group = self.get_object()
        shipment_id = request.data.get('shipment_id')
        invoice_ref = request.data.get('invoice_reference', '')
        parcels = int(request.data.get('parcel_count', 1))
        weight_kg = float(request.data.get('weight_kg', 0.0))

        shipment = None
        if shipment_id:
            from apps.courier.models import Shipment
            shipment = Shipment.objects.filter(tenant=request.tenant, id=shipment_id).first()

        from apps.warehouse.services import ShipmentConsolidationService
        item = ShipmentConsolidationService.add_item(
            group=group,
            shipment=shipment,
            invoice_ref=invoice_ref,
            parcels=parcels,
            weight_kg=weight_kg
        )
        from apps.warehouse.serializers import ConsolidatedShipmentItemSerializer
        return Response(ConsolidatedShipmentItemSerializer(item).data, status=status.HTTP_201_CREATED)

