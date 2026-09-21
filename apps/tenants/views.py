from rest_framework import viewsets, status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import action
from django.db import models
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from apps.tenants.models import Tenant, TenantUser, Role, Permission, Vertical, TenantStatus
from apps.tenants.serializers import (
    TenantSerializer,
    TenantUserSerializer,
    RoleSerializer,
    PermissionSerializer,
    VerticalSerializer,
    TenantProvisionSerializer,
)
from apps.tenants.services import TenantProvisioningService
from apps.core.permissions import IsPlatformAdmin, HasTenantAccess, HasPermission
from apps.core.pagination import StandardPagination
from apps.audit.services import AuditService


class TenantProvisionView(APIView):
    """
    POST /api/v1/platform/tenants/provision/
    Atomically provisions a new tenant organization, subscription, and admin account.
    """
    permission_classes = [permissions.AllowAny]
    serializer_class = TenantProvisionSerializer

    def post(self, request):
        serializer = TenantProvisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        result = TenantProvisioningService.provision(
            company_name=data['company_name'],
            admin_email=data['admin_email'],
            admin_password=data['admin_password'],
            admin_first_name=data.get('admin_first_name', 'Admin'),
            admin_last_name=data.get('admin_last_name', 'User'),
            package_code=data.get('package_code', 'CORPORATE'),
            addon_codes=data.get('addon_codes', []),
            vertical_codes=data.get('vertical_codes', []),
            phone=data.get('phone', ''),
            address=data.get('address', ''),
            billing_cycle=data.get('billing_cycle', 'MONTHLY'),
            actor=request.user if request.user.is_authenticated else None
        )

        return Response({
            'message': 'Tenant successfully provisioned and activated.',
            'tenant_id': result['tenant_id'],
            'company_name': result['tenant'].company_name,
            'slug': result['slug'],
            'status': result['tenant'].status,
            'admin_email': result['admin_user'].email,
        }, status=status.HTTP_201_CREATED)


class PlatformTenantViewSet(viewsets.ModelViewSet):
    """
    Platform administrator ViewSet for managing all tenant accounts.
    """
    queryset = Tenant.objects.all().select_related('package').prefetch_related('verticals')
    serializer_class = TenantSerializer
    permission_classes = [IsPlatformAdmin]
    pagination_class = StandardPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'package__code']
    search_fields = ['company_name', 'tenant_id', 'slug', 'email']
    ordering_fields = ['created_at', 'company_name']

    @action(detail=True, methods=['post'])
    def suspend(self, request, pk=None):
        tenant = self.get_object()
        tenant.status = TenantStatus.SUSPENDED
        tenant.save(update_fields=['status'])
        AuditService.record(
            action='TENANT_SUSPENDED',
            actor=request.user,
            tenant=tenant,
            target_type='Tenant',
            target_id=str(tenant.id)
        )
        return Response({'message': f"Tenant '{tenant.company_name}' has been suspended."})

    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        tenant = self.get_object()
        tenant.status = TenantStatus.ACTIVE
        tenant.save(update_fields=['status'])
        AuditService.record(
            action='TENANT_ACTIVATED',
            actor=request.user,
            tenant=tenant,
            target_type='Tenant',
            target_id=str(tenant.id)
        )
        return Response({'message': f"Tenant '{tenant.company_name}' has been activated."})


class TenantUserViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing team members within the active tenant workspace.
    """
    serializer_class = TenantUserSerializer
    permission_classes = [HasTenantAccess, HasPermission]
    required_permission = 'tenant.manage'
    pagination_class = StandardPagination

    def get_queryset(self):
        tenant = getattr(self.request, 'tenant', None)
        if not tenant:
            return TenantUser.objects.none()
        return TenantUser.objects.filter(tenant=tenant).select_related('user', 'role')

    def perform_create(self, serializer):
        serializer.save(tenant=self.request.tenant)


class RoleViewSet(viewsets.ReadOnlyModelViewSet):
    """
    View roles available to the current tenant (system roles + tenant custom roles).
    """
    serializer_class = RoleSerializer
    permission_classes = [HasTenantAccess]
    pagination_class = StandardPagination

    def get_queryset(self):
        tenant = getattr(self.request, 'tenant', None)
        return Role.objects.filter(models.Q(tenant=None) | models.Q(tenant=tenant)).prefetch_related('role_permissions__permission')


class PermissionListView(APIView):
    """
    List all platform permission definitions.
    """
    permission_classes = [HasTenantAccess]

    def get(self, request):
        perms = Permission.objects.all().order_by('module', 'code')
        return Response(PermissionSerializer(perms, many=True).data)


class TenantMetadataView(APIView):
    """
    GET /api/v1/tenants/metadata/
    Exposes authoritative vertical and module configuration enabling
    dynamic, data-driven frontend UI rendering without hardcoded frontend logic.
    """
    permission_classes = [HasTenantAccess]

    def get(self, request):
        tenant = request.tenant
        user = request.user
        tenant_user = getattr(request, 'tenant_user', None)

        from apps.subscriptions.services import get_tenant_effective_features
        from apps.tenants.serializers import TenantSerializer, VerticalSerializer

        entitlements = get_tenant_effective_features(tenant)
        user_perms = tenant_user.get_all_permissions() if tenant_user else []

        verticals_data = VerticalSerializer(tenant.verticals.all(), many=True).data

        # Determine enabled modules based on effective features and verticals
        modules = set(['fleet', 'drivers', 'crm', 'trips', 'finance'])
        if 'warehouse' in entitlements['effective_features']:
            modules.add('warehouse')
        if 'contracts' in entitlements['effective_features']:
            modules.add('contracts')
        if 'courier' in entitlements['effective_features'] or any(v['code'] == 'COURIER' for v in verticals_data):
            modules.add('courier')
        if 'shuttle' in entitlements['effective_features'] or any(v['code'] == 'SHUTTLE' for v in verticals_data):
            modules.add('shuttle')

        return Response({
            'tenant': {
                'id': str(tenant.id),
                'tenant_id': tenant.tenant_id,
                'company_name': tenant.company_name,
                'slug': tenant.slug,
                'status': tenant.status,
            },
            'verticals': verticals_data,
            'package': {
                'code': tenant.package.code if tenant.package else None,
                'name': tenant.package.name if tenant.package else None,
            },
            'features': entitlements['effective_features'],
            'addons': entitlements['addon_features'],
            'custom_features': entitlements['overrides'],
            'permissions': user_perms,
            'modules': sorted(list(modules))
        })


class PlatformTenantUpgradeView(APIView):
    """
    POST /api/v1/platform/tenants/<tenant_id>/upgrade/
    Platform admin endpoint to upgrade/downgrade a tenant's subscription tier.
    """
    permission_classes = [IsPlatformAdmin]

    def post(self, request, tenant_id=None):
        from apps.subscriptions.services import SubscriptionUpgradeService
        from apps.core.exceptions import BusinessValidationError

        # Resolve tenant by public tenant_id or UUID
        tenant = Tenant.objects.filter(tenant_id=str(tenant_id)).first()
        if not tenant:
            try:
                import uuid
                tenant = Tenant.objects.filter(id=uuid.UUID(str(tenant_id))).first()
            except (ValueError, TypeError):
                tenant = None
        if not tenant:
            raise BusinessValidationError(
                "Tenant not found.",
                code='TENANT_NOT_FOUND',
                status_code=404,
            )

        package_code = request.data.get('package_tier', '').upper() or request.data.get('package_code', '').upper()
        billing_cycle = request.data.get('billing_cycle')

        if not package_code:
            raise BusinessValidationError(
                "package_tier or package_code is required.",
                code='VALIDATION_ERROR',
            )

        # Normalize billing cycle
        if billing_cycle:
            mapping = {'monthly': 'MONTHLY', 'annually': 'YEARLY', 'yearly': 'YEARLY'}
            billing_cycle = mapping.get(billing_cycle.lower(), billing_cycle.upper())

        result = SubscriptionUpgradeService.upgrade(
            tenant=tenant,
            target_package_code=package_code,
            billing_cycle=billing_cycle,
            actor=request.user,
        )

        from apps.subscriptions.serializers import SubscriptionSerializer
        sub = result['subscription']
        pkg = result.get('target_package') or getattr(sub, 'package', None)
        mrr = float(pkg.price_monthly) if (pkg and pkg.price_monthly) else 0.0

        return Response({
            'success': True,
            'message': result['message'],
            'data': {
                'tenant_id': tenant.tenant_id,
                'package_tier': package_code.lower(),
                'mrr': mrr,
                'features': result['effective_features'],
                'effective_features': result['effective_features'],
                'subscription': SubscriptionSerializer(sub).data,
            }
        })
