from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.warehouse.views import (
    WarehouseViewSet,
    SupplierViewSet,
    SparePartViewSet,
    PurchaseOrderViewSet,
    InventoryTransactionViewSet,
    WarehouseDeliveryViewSet,
    CrossDockOperationViewSet,
    ConsolidationGroupViewSet,
)

router = DefaultRouter()
router.register('warehouses', WarehouseViewSet, basename='warehouses')
router.register('suppliers', SupplierViewSet, basename='suppliers')
router.register('parts', SparePartViewSet, basename='parts')
router.register('purchase-orders', PurchaseOrderViewSet, basename='purchase_orders')
router.register('transactions', InventoryTransactionViewSet, basename='inventory_transactions')
router.register('deliveries', WarehouseDeliveryViewSet, basename='warehouse_deliveries')
router.register('cross-dock', CrossDockOperationViewSet, basename='cross_dock_operations')
router.register('consolidation', ConsolidationGroupViewSet, basename='consolidation_groups')

app_name = 'warehouse'

urlpatterns = [
    path('warehouse/', include(router.urls)),
]

