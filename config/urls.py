from django.contrib import admin
from django.urls import path, include
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)


class HealthCheckView(APIView):
    """
    Service liveness and readiness probe.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({
            'status': 'healthy',
            'service': 'OmniCore Backend',
            'version': '1.0.0',
        })


urlpatterns = [
    path('admin/', admin.site.urls),

    # OpenAPI 3.0 Documentation
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),

    # Health Probe
    path('api/v1/health/', HealthCheckView.as_view(), name='health_check'),

    # Auth & Identity
    path('api/v1/auth/', include('apps.accounts.urls', namespace='accounts')),

    # Enterprise Domains
    path('api/v1/', include('apps.tenants.urls', namespace='tenants')),
    path('api/v1/', include('apps.subscriptions.urls', namespace='subscriptions')),
    path('api/v1/', include('apps.fleet.urls', namespace='fleet')),
    path('api/v1/', include('apps.drivers.urls', namespace='drivers')),
    path('api/v1/', include('apps.crm.urls', namespace='crm')),
    path('api/v1/', include('apps.trips.urls', namespace='trips')),
    path('api/v1/', include('apps.contracts.urls', namespace='contracts')),
    path('api/v1/', include('apps.maintenance.urls', namespace='maintenance')),
    path('api/v1/', include('apps.warehouse.urls', namespace='warehouse')),
    path('api/v1/', include('apps.finance.urls', namespace='finance')),
    path('api/v1/', include('apps.hr.urls', namespace='hr')),
    path('api/v1/', include('apps.insurance.urls', namespace='insurance')),
    path('api/v1/', include('apps.marketing.urls', namespace='marketing')),
    path('api/v1/', include('apps.notifications.urls', namespace='notifications')),
    path('api/v1/', include('apps.reports.urls', namespace='reports')),
    path('api/v1/', include('apps.audit.urls', namespace='audit')),
    path('api/v1/courier/', include('apps.courier.urls')),
    path('api/v1/shuttle/', include('apps.shuttle.urls')),
    path('api/v1/', include('apps.website.urls')),
]

