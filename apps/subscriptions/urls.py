from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.subscriptions.views import (
    PackageViewSet,
    AddonViewSet,
    TenantSubscriptionView,
    TenantFeatureOverrideView,
    TenantEffectiveEntitlementsView,
    PlatformSubscriptionUpgradeView,
)

router = DefaultRouter()
router.register('packages', PackageViewSet, basename='packages')
router.register('addons', AddonViewSet, basename='addons')

app_name = 'subscriptions'

urlpatterns = [
    # Tenant self-service
    path('subscriptions/current/', TenantSubscriptionView.as_view(), name='subscription_current'),
    path('subscriptions/upgrade/', TenantSubscriptionView.as_view(), name='subscription_upgrade'),

    # Platform administrative feature overrides & upgrades
    path('platform/tenants/<str:tenant_id>/features/override/', TenantFeatureOverrideView.as_view(), name='tenant_feature_override'),
    path('platform/tenants/<str:tenant_id>/entitlements/', TenantEffectiveEntitlementsView.as_view(), name='tenant_entitlements'),
    path('platform/subscriptions/<str:pk>/upgrade/', PlatformSubscriptionUpgradeView.as_view(), name='platform_subscription_upgrade'),

    path('', include(router.urls)),
]
