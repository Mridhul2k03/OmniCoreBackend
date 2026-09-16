from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.courier.views import (
    HubViewSet, CourierAgentViewSet, ShipmentViewSet,
    ShipmentPickupViewSet, SortingRecordViewSet, DeliveryViewSet,
    ProofOfDeliveryViewSet, CourierCommissionViewSet,
    CourierExpenseViewSet, CourierPayoutViewSet
)

router = DefaultRouter()
router.register(r'hubs', HubViewSet, basename='courier-hub')
router.register(r'agents', CourierAgentViewSet, basename='courier-agent')
router.register(r'shipments', ShipmentViewSet, basename='courier-shipment')
router.register(r'pickups', ShipmentPickupViewSet, basename='courier-pickup')
router.register(r'sorting', SortingRecordViewSet, basename='courier-sorting')
router.register(r'deliveries', DeliveryViewSet, basename='courier-delivery')
router.register(r'pod', ProofOfDeliveryViewSet, basename='courier-pod')
router.register(r'commissions', CourierCommissionViewSet, basename='courier-commission')
router.register(r'expenses', CourierExpenseViewSet, basename='courier-expense')
router.register(r'payouts', CourierPayoutViewSet, basename='courier-payout')

urlpatterns = [
    path('', include(router.urls)),
]
