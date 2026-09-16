from rest_framework import viewsets, permissions
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from apps.audit.models import AuditLog
from apps.audit.serializers import AuditLogSerializer
from apps.core.permissions import HasTenantAccess, HasPermission
from apps.core.pagination import StandardPagination


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Immutable audit trail view.
    Platform admins can view all logs; tenant managers can view tenant-scoped logs.
    """
    serializer_class = AuditLogSerializer
    pagination_class = StandardPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['action', 'target_type', 'target_id']
    search_fields = ['action', 'actor__email', 'target_id']
    ordering_fields = ['timestamp']

    def get_queryset(self):
        user = self.request.user
        if not user or not user.is_authenticated:
            return AuditLog.objects.none()

        if user.is_superuser or getattr(user, 'is_platform_admin', False):
            tenant_param = self.request.query_params.get('tenant')
            if tenant_param:
                return AuditLog.objects.filter(tenant_id=tenant_param).select_related('actor', 'tenant')
            return AuditLog.objects.all().select_related('actor', 'tenant')

        tenant = getattr(self.request, 'tenant', None)
        if not tenant:
            return AuditLog.objects.none()

        return AuditLog.objects.filter(tenant=tenant).select_related('actor', 'tenant')
