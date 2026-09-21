from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.tenants.views import (
    TenantProvisionView,
    PlatformTenantViewSet,
    TenantUserViewSet,
    RoleViewSet,
    PermissionListView,
    TenantMetadataView,
    PlatformTenantUpgradeView,
)

router = DefaultRouter()
router.register('users', TenantUserViewSet, basename='tenant_users')
router.register('roles', RoleViewSet, basename='roles')

platform_router = DefaultRouter()
platform_router.register('tenants', PlatformTenantViewSet, basename='platform_tenants')

app_name = 'tenants'

urlpatterns = [
    path('platform/tenants/provision/', TenantProvisionView.as_view(), name='tenant_provision'),
    path('platform/tenants/<str:tenant_id>/upgrade/', PlatformTenantUpgradeView.as_view(), name='platform_tenant_upgrade'),
    path('platform/', include(platform_router.urls)),
    path('tenants/permissions/', PermissionListView.as_view(), name='permission_list'),
    path('tenants/metadata/', TenantMetadataView.as_view(), name='tenant_metadata'),
    path('tenants/', include(router.urls)),
]

