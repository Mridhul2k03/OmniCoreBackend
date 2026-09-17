from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.fleet.views import VehicleViewSet, VehicleCategoryViewSet, VehicleDocumentViewSet

router = DefaultRouter()
router.register('categories', VehicleCategoryViewSet, basename='vehicle_categories')
router.register('documents', VehicleDocumentViewSet, basename='vehicle_documents')
router.register('', VehicleViewSet, basename='vehicles')

app_name = 'fleet'

urlpatterns = [
    path('vehicles/', include(router.urls)),
    path('fleet/vehicles/', include(router.urls)),
]
