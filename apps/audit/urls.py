from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.audit.views import AuditLogViewSet

router = DefaultRouter()
router.register('', AuditLogViewSet, basename='audit_logs')

app_name = 'audit'

urlpatterns = [
    path('audit/', include(router.urls)),
]
