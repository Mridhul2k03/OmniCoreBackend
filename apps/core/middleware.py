from django.utils.deprecation import MiddlewareMixin
from django.db import models


def resolve_tenant_context(request):
    """
    Core function to resolve the active tenant and tenant user membership.
    Works seamlessly across Django middleware and DRF API request lifecycles.
    """
    if hasattr(request, '_tenant_resolved') and request._tenant_resolved:
        return getattr(request, 'tenant', None), getattr(request, 'tenant_user', None)

    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        request.tenant = None
        request.tenant_user = None
        return None, None

    from apps.tenants.models import Tenant, TenantUser

    # Look for tenant in headers or query params
    tenant_header = None
    if hasattr(request, 'headers'):
        tenant_header = request.headers.get('X-Tenant-ID')
    if not tenant_header and hasattr(request, 'META'):
        tenant_header = request.META.get('HTTP_X_TENANT_ID')
    if not tenant_header and hasattr(request, 'GET'):
        tenant_header = request.GET.get('tenant_id')

    if tenant_header:
        tenant = Tenant.objects.filter(
            models.Q(tenant_id__iexact=str(tenant_header).strip()) |
            models.Q(slug__iexact=str(tenant_header).strip()) |
            models.Q(id__iexact=str(tenant_header).strip())
        ).first()

        if tenant:
            tenant_user = TenantUser.objects.filter(
                user=user,
                tenant=tenant,
                is_active=True
            ).select_related('tenant', 'role').first()

            if tenant_user or user.is_superuser or getattr(user, 'is_platform_admin', False):
                request.tenant = tenant
                request.tenant_user = tenant_user
                request._tenant_resolved = True
                return tenant, tenant_user

    # Fallback to user's primary or first active membership
    primary_membership = TenantUser.objects.filter(
        user=user,
        is_active=True
    ).select_related('tenant', 'role').order_by('-is_primary', '-created_at').first()

    if primary_membership:
        request.tenant = primary_membership.tenant
        request.tenant_user = primary_membership
        request._tenant_resolved = True
        return request.tenant, request.tenant_user

    request.tenant = None
    request.tenant_user = None
    request._tenant_resolved = True
    return None, None


class TenantResolutionMiddleware(MiddlewareMixin):
    """
    Django middleware wrapper for resolving tenant context on incoming HTTP requests.
    """
    def process_request(self, request):
        resolve_tenant_context(request)
