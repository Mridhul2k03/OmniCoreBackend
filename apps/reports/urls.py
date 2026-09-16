from django.urls import path
from apps.reports.views import (
    PlatformDashboardView,
    TenantDashboardView,
    ExportVehiclesCSVView,
    ExportTripsCSVView,
)

app_name = 'reports'

urlpatterns = [
    path('platform/dashboard/', PlatformDashboardView.as_view(), name='platform_dashboard'),
    path('dashboard/', TenantDashboardView.as_view(), name='tenant_dashboard'),
    path('reports/vehicles/csv/', ExportVehiclesCSVView.as_view(), name='export_vehicles_csv'),
    path('reports/trips/csv/', ExportTripsCSVView.as_view(), name='export_trips_csv'),
]
