from rest_framework import viewsets, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from apps.subscriptions.models import Package, Addon, Subscription, Feature, TenantFeatureOverride
from apps.subscriptions.serializers import PackageSerializer, AddonSerializer, SubscriptionSerializer
from apps.subscriptions.services import (
    sync_tenant_features,
    get_tenant_effective_features,
    SubscriptionUpgradeService,
)
from apps.core.permissions import HasTenantAccess, IsPlatformAdmin
from apps.core.exceptions import BusinessValidationError
from apps.audit.services import AuditService
from apps.tenants.models import Tenant


class PackageViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Package.objects.filter(is_active=True).prefetch_related('features')
    serializer_class = PackageSerializer
    permission_classes = [permissions.AllowAny]


class AddonViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Addon.objects.filter(is_active=True).prefetch_related('features')
    serializer_class = AddonSerializer
    permission_classes = [permissions.AllowAny]


class TenantSubscriptionView(APIView):
    """
    GET /api/v1/subscriptions/current/
    POST /api/v1/subscriptions/upgrade/
    """
    permission_classes = [HasTenantAccess]

    def get(self, request):
        tenant = request.tenant
        subscription = getattr(tenant, 'subscription', None)
        if not subscription:
            return Response({'subscription': None})
        serializer = SubscriptionSerializer(subscription)
        return Response(serializer.data)

    def post(self, request):
        """
        Add add-on or switch package tier
        """
        tenant = request.tenant
        package_code = request.data.get('package_code')
        billing_cycle = request.data.get('billing_cycle')

        if package_code:
            result = SubscriptionUpgradeService.upgrade(
                tenant=tenant,
                target_package_code=package_code,
                billing_cycle=billing_cycle,
                actor=request.user
            )
            return Response({
                'message': result['message'],
                'subscription': SubscriptionSerializer(result['subscription']).data,
                'effective_features': result['effective_features']
            })

        # Addons only
        subscription = getattr(tenant, 'subscription', None)
        if not subscription:
            raise BusinessValidationError("No active subscription found for tenant.")

        addon_codes = request.data.get('addon_codes', [])
        if addon_codes:
            for a_code in addon_codes:
                addon = Addon.objects.filter(code=a_code, is_active=True).first()
                if addon:
                    subscription.addons.add(addon)
            subscription.save()
            sync_tenant_features(tenant)

        return Response({
            'message': 'Subscription updated successfully.',
            'subscription': SubscriptionSerializer(subscription).data
        })


class TenantFeatureOverrideView(APIView):
    """
    POST /api/v1/platform/tenants/{tenant_id}/features/override/
    Super Admin endpoint to grant or revoke an isolated feature for a specific tenant
    without modifying the tenant's baseline package.
    """
    permission_classes = [IsPlatformAdmin]

    def post(self, request, tenant_id=None):
        tenant = Tenant.objects.filter(id=tenant_id).first() or Tenant.objects.filter(tenant_id=tenant_id).first()
        if not tenant:
            raise BusinessValidationError("Tenant not found.")

        feature_code = request.data.get('feature_code')
        enabled = request.data.get('enabled', True)
        reason = request.data.get('reason', 'Administrative grant')
        expires_at = request.data.get('expires_at')

        feature = Feature.objects.filter(code=feature_code).first()
        if not feature:
            raise BusinessValidationError(f"Feature '{feature_code}' does not exist.")

        override, created = TenantFeatureOverride.objects.update_or_create(
            tenant=tenant,
            feature=feature,
            defaults={
                'enabled': enabled,
                'reason': reason,
                'expires_at': expires_at,
                'created_by': request.user
            }
        )

        AuditService.record(
            action='CUSTOM_FEATURE_OVERRIDE',
            actor=request.user,
            tenant=tenant,
            target_type='Feature',
            target_id=str(feature.id),
            after_snapshot={
                'feature_code': feature.code,
                'enabled': enabled,
                'expires_at': str(expires_at),
                'reason': reason
            }
        )

        # Invalidate cache
        from django.core.cache import cache
        cache.delete(f"tenant_feature_{tenant.id}_{feature.code}")

        entitlements = get_tenant_effective_features(tenant)

        return Response({
            'message': f"Feature '{feature.code}' override set to {enabled} for {tenant.company_name}.",
            'tenant_id': tenant.tenant_id,
            'effective_features': entitlements['effective_features'],
            'overrides': entitlements['overrides']
        })


class TenantEffectiveEntitlementsView(APIView):
    """
    GET /api/v1/platform/tenants/{tenant_id}/entitlements/
    Inspects effective entitlements and origins (package, addon, override).
    """
    permission_classes = [IsPlatformAdmin]

    def get(self, request, tenant_id=None):
        tenant = Tenant.objects.filter(id=tenant_id).first() or Tenant.objects.filter(tenant_id=tenant_id).first()
        if not tenant:
            raise BusinessValidationError("Tenant not found.")

        entitlements = get_tenant_effective_features(tenant)
        return Response({
            'tenant_id': tenant.tenant_id,
            'company_name': tenant.company_name,
            'package': tenant.package.name if tenant.package else None,
            **entitlements
        })


class PlatformSubscriptionUpgradeView(APIView):
    """
    POST /api/v1/platform/subscriptions/{id}/upgrade/
    Platform admin endpoint to execute a transactional package upgrade for any subscription.
    """
    permission_classes = [IsPlatformAdmin]

    def post(self, request, pk=None):
        subscription = Subscription.objects.filter(id=pk).select_related('tenant').first()
        if not subscription:
            raise BusinessValidationError("Subscription not found.")

        target_package_code = request.data.get('package_code')
        billing_cycle = request.data.get('billing_cycle')

        result = SubscriptionUpgradeService.upgrade(
            tenant=subscription.tenant,
            target_package_code=target_package_code,
            billing_cycle=billing_cycle,
            actor=request.user
        )

        return Response({
            'message': result['message'],
            'subscription': SubscriptionSerializer(result['subscription']).data,
            'effective_features': result['effective_features']
        })
