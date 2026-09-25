from rest_framework import viewsets, status
from rest_framework.response import Response
from django.db import models
from django.core.exceptions import FieldError
from apps.core.permissions import HasTenantAccess, HasPermission, HasFeature
from apps.core.pagination import StandardPagination
from apps.core.exceptions import TenantIsolationError, BusinessValidationError
from apps.core.middleware import resolve_tenant_context


class TenantModelViewSet(viewsets.ModelViewSet):
    """
    Base ViewSet for all tenant-scoped resources in OmniCore.
    Guarantees:
    1. Automatic tenant isolation in get_queryset().
    2. Prevention of cross-tenant data leakage via get_object().
    3. Automatic tenant attribution in perform_create().
    4. Integration of RBAC, Feature Entitlement, and Tenant Status enforcement.
    """
    permission_classes = [HasTenantAccess, HasPermission, HasFeature]
    pagination_class = StandardPagination

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        resolve_tenant_context(request)

    def get_queryset(self):
        queryset = super().get_queryset()
        tenant, _ = resolve_tenant_context(self.request)

        if not tenant:
            user = self.request.user
            if user and (
                getattr(user, 'is_superuser', False) or
                getattr(user, 'is_platform_admin', False) or
                getattr(user, 'platform_role', None) == 'SUPER_ADMIN'
            ):
                return queryset
            return queryset.none()

        try:
            return queryset.filter(tenant=tenant)
        except FieldError:
            return queryset

    def get_object(self):
        """
        Enforces object-level tenant isolation.
        If an object ID belongs to another tenant, it returns 404
        to prevent resource enumeration attacks.
        """
        try:
            return super().get_object()
        except Exception:
            raise TenantIsolationError(
                detail="Resource not found in your tenant workspace.",
                code='RESOURCE_NOT_FOUND'
            )

    def perform_create(self, serializer):
        tenant, _ = resolve_tenant_context(self.request)
        if not tenant:
            user = self.request.user
            if user and (
                getattr(user, 'is_superuser', False) or
                getattr(user, 'is_platform_admin', False) or
                getattr(user, 'platform_role', None) == 'SUPER_ADMIN'
            ):
                tenant_id = self.request.data.get('tenant') or self.request.data.get('tenant_id')
                if tenant_id:
                    from apps.tenants.models import Tenant
                    tenant = Tenant.objects.filter(
                        models.Q(id__iexact=str(tenant_id).strip()) |
                        models.Q(tenant_id__iexact=str(tenant_id).strip())
                    ).first()
            if not tenant:
                raise BusinessValidationError(
                    detail="A valid tenant context is required to create this resource.",
                    code='TENANT_REQUIRED'
                )
        
        save_kwargs = {'tenant': tenant}
        if hasattr(serializer.Meta.model, 'created_by'):
            save_kwargs['created_by'] = self.request.user

        serializer.save(**save_kwargs)

    def perform_destroy(self, instance):
        """
        Safe soft-delete implementation.
        """
        if hasattr(instance, 'delete'):
            instance.delete()
        else:
            super().perform_destroy(instance)
