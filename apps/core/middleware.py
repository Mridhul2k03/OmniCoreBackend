from django.utils.deprecation import MiddlewareMixin
from django.db import models


def resolve_tenant_context(request):
    """
    Core function to resolve the active tenant and tenant user membership.
    Works seamlessly across Django middleware and DRF API request lifecycles.

    Multi-Tenant Scoping Rules:
    - Inspects 'X-Tenant-ID' in request headers (or META / query params).
    - If present, validates and binds request.tenant to the corresponding Tenant instance.
    - For Super Admins (is_platform_admin=True, is_superuser=True, or role='SUPER_ADMIN'),
      allows cross-tenant queries if X-Tenant-ID is omitted or set to 'all'.
    """
    if hasattr(request, '_tenant_resolved') and request._tenant_resolved:
        return getattr(request, 'tenant', None), getattr(request, 'tenant_user', None)

    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        request.tenant = None
        request.tenant_user = None
        return None, None

    from apps.tenants.models import Tenant, TenantUser

    is_super = (
        getattr(user, 'is_superuser', False) or
        getattr(user, 'is_platform_admin', False) or
        getattr(user, 'platform_role', None) == 'SUPER_ADMIN'
    )

    # Look for tenant in headers or query params
    tenant_header = None
    if hasattr(request, 'headers'):
        tenant_header = request.headers.get('X-Tenant-ID')
    if not tenant_header and hasattr(request, 'META'):
        tenant_header = request.META.get('HTTP_X_TENANT_ID')
    if not tenant_header and hasattr(request, 'GET'):
        tenant_header = request.GET.get('tenant_id')

    if tenant_header:
        tenant_val = str(tenant_header).strip()
        if is_super and tenant_val.lower() == 'all':
            request.tenant = None
            request.tenant_user = None
            request._tenant_resolved = True
            return None, None

        tenant = Tenant.objects.filter(
            models.Q(id__iexact=tenant_val) |
            models.Q(tenant_id__iexact=tenant_val) |
            models.Q(slug__iexact=tenant_val)
        ).first()

        if tenant:
            tenant_user = TenantUser.objects.filter(
                user=user,
                tenant=tenant,
                is_active=True
            ).select_related('tenant', 'role').first()

            if tenant_user or is_super:
                request.tenant = tenant
                request.tenant_user = tenant_user
                request._tenant_resolved = True
                return tenant, tenant_user

    # If tenant_header is omitted or not found:
    # Super Admins: cross-tenant access allowed when omitted
    if is_super:
        request.tenant = None
        request.tenant_user = None
        request._tenant_resolved = True
        return None, None

    # Fallback to user's primary or first active membership for standard tenant users
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


class TenantHeaderMiddleware(MiddlewareMixin):
    """
    Middleware inspecting 'X-Tenant-ID' header, validating and binding request.tenant.
    For Super Admins (is_platform_admin=True or role='SUPER_ADMIN'), allows cross-tenant
    queries if X-Tenant-ID is omitted or set to 'all'.
    """
    def process_request(self, request):
        resolve_tenant_context(request)


# Backward compatibility alias
TenantResolutionMiddleware = TenantHeaderMiddleware

