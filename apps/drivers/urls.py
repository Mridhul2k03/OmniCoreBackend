from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.drivers.views import DriverViewSet, DriverDocumentViewSet, AttendanceViewSet, DriverIncidentViewSet

router = DefaultRouter()
router.register('documents', DriverDocumentViewSet, basename='driver_documents')
router.register('attendance', AttendanceViewSet, basename='attendance')
router.register('incidents', DriverIncidentViewSet, basename='driver_incidents')
router.register('', DriverViewSet, basename='drivers')

app_name = 'drivers'

urlpatterns = [
    path('drivers/', include(router.urls)),
]
