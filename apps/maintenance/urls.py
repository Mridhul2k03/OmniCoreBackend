from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.maintenance.views import (
    MaintenanceRecordViewSet,
    MaintenanceScheduleViewSet,
    BreakdownViewSet,
    AccidentViewSet,
    RepairOrderViewSet,
)

router = DefaultRouter()
router.register('records', MaintenanceRecordViewSet, basename='maintenance_records')
router.register('schedules', MaintenanceScheduleViewSet, basename='maintenance_schedules')
router.register('breakdowns', BreakdownViewSet, basename='breakdowns')
router.register('accidents', AccidentViewSet, basename='accidents')
router.register('repair-orders', RepairOrderViewSet, basename='repair_orders')

app_name = 'maintenance'

urlpatterns = [
    path('maintenance/', include(router.urls)),
]
