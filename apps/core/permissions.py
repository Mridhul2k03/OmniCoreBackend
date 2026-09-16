from rest_framework.permissions import BasePermission
from apps.core.exceptions import (
    TenantSuspendedError,
    PermissionDeniedError,
    FeatureNotEntitledError
)
from apps.core.middleware import resolve_tenant_context


class IsPlatformAdmin(BasePermission):
    """
    Allows access only to global platform administrators.
    """
    def has_permission(self, request, view):
        user = request.user
        return bool(
            user and 
            user.is_authenticated and 
            (user.is_superuser or getattr(user, 'is_platform_admin', False))
        )


class HasTenantAccess(BasePermission):
    """
    Validates that:
    1. User is authenticated.
    2. User is an active member of request.tenant.
    3. The tenant's status is ACTIVE or TRIAL.
    """
    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False

        # Super admin bypass for platform administration
        if user.is_superuser or getattr(user, 'is_platform_admin', False):
            return True

        tenant, tenant_user = resolve_tenant_context(request)
        if not tenant:
            raise PermissionDeniedError(
                detail="A valid tenant workspace could not be identified for this request.",
                code='TENANT_NOT_FOUND'
            )

        # Check tenant status
        if tenant.status not in ['ACTIVE', 'TRIAL']:
            raise TenantSuspendedError(
                detail=f"Tenant '{tenant.company_name}' is currently {tenant.status.lower()}. Access blocked.",
                code='TENANT_NOT_ACTIVE'
            )

        # Check tenant membership
        if not tenant_user or not tenant_user.is_active:
            raise PermissionDeniedError(
                detail="You do not have an active membership in this tenant organization.",
                code='MEMBERSHIP_INACTIVE'
            )

        return True


class HasPermission(BasePermission):
    """
    Permission class checking for granular RBAC permission codes
    (e.g., 'vehicle.view', 'trip.dispatch', 'inventory.adjust').
    """
    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False

        if user.is_superuser or getattr(user, 'is_platform_admin', False):
            return True

        required_perm = getattr(view, 'required_permission', None)
        required_perms = getattr(view, 'required_permissions', [])
        if required_perm:
            required_perms = [required_perm] + list(required_perms)

        if not required_perms:
            return True

        tenant, tenant_user = resolve_tenant_context(request)
        if not tenant_user:
            return False

        # Tenant admin has all tenant permissions
        if getattr(tenant_user, 'role', None) and tenant_user.role.code == 'TENANT_ADMIN':
            return True

        user_perms = tenant_user.get_all_permissions()
        for perm in required_perms:
            if perm not in user_perms:
                raise PermissionDeniedError(
                    detail=f"Permission code '{perm}' is required for this action.",
                    code='MISSING_PERMISSION'
                )

        return True


class HasFeature(BasePermission):
    """
    Entitlement permission class checking if the tenant's package or active add-ons
    entitle them to use this module (e.g. 'warehouse', 'contracts', 'telematics').
    """
    def has_permission(self, request, view):
        required_feature = getattr(view, 'required_feature', None)
        if not required_feature:
            return True

        user = request.user
        if user and user.is_authenticated and (user.is_superuser or getattr(user, 'is_platform_admin', False)):
            return True

        tenant, _ = resolve_tenant_context(request)
        if not tenant:
            return False

        from apps.subscriptions.services import tenant_has_feature
        if not tenant_has_feature(tenant, required_feature):
            raise FeatureNotEntitledError(
                detail=f"The '{required_feature}' module is not enabled for your subscription tier. Upgrade your package or enable the add-on.",
                code='FEATURE_NOT_ENTITLED'
            )

        return True
