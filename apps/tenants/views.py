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
    TenantProfileSerializer,
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

    @action(detail=True, methods=['patch'], url_path='verticals')
    def verticals(self, request, pk=None):
        """Replace a tenant's licensed vertical list using UI vertical codes."""
        codes = request.data.get('vertical_codes')
        if not isinstance(codes, list) or any(not isinstance(code, str) or not code.strip() for code in codes):
            return Response(
                {'code': 'VALIDATION_ERROR', 'message': 'vertical_codes must be a list of non-empty strings.',
                 'fields': {'vertical_codes': ['Provide a list of vertical codes.']}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        normalized_codes = list(dict.fromkeys(code.strip().lower() for code in codes))
        verticals = []
        for code in normalized_codes:
            vertical, _ = Vertical.objects.get_or_create(
                code=code,
                defaults={'name': code.replace('_', ' ').title()},
            )
            if not vertical.is_active:
                return Response(
                    {'code': 'VALIDATION_ERROR', 'message': f"Vertical '{code}' is inactive.",
                     'fields': {'vertical_codes': [f"'{code}' is not available."]}},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            verticals.append(vertical)
        tenant = self.get_object()
        tenant.verticals.set(verticals)
        return Response(TenantSerializer(tenant, context=self.get_serializer_context()).data)


class TenantUserViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing team members within the active tenant workspace.
    """
    serializer_class = TenantUserSerializer
    permission_classes = [HasTenantAccess, HasPermission]
    required_permission = 'tenant.manage'
    pagination_class = StandardPagination

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if request.method in {'POST', 'PUT', 'PATCH', 'DELETE'}:
            membership = getattr(request, 'tenant_user', None)
            if not membership or not membership.is_primary or not membership.role or membership.role.code != 'TENANT_ADMIN':
                from apps.core.exceptions import PermissionDeniedError
                raise PermissionDeniedError(
                    detail='Only the primary tenant administrator can manage employee access.',
                    code='PRIMARY_ADMIN_REQUIRED',
                )

    def create(self, request, *args, **kwargs):
        return Response(
            {'code': 'INVITATION_REQUIRED', 'message': 'Create employee accounts through the HR invitation flow.'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

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
        # Backfill the Staff template once for tenants created before that role existed.
        if not Role.objects.filter(tenant=None, code='STAFF').exists():
            from apps.tenants.services import seed_platform_roles_and_permissions
            seed_platform_roles_and_permissions()
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


class TenantProfileView(APIView):
    """Read and update the active tenant's editable organization profile."""
    permission_classes = [HasTenantAccess, HasPermission]
    required_permission = 'tenant.manage'

    def get(self, request):
        return Response(TenantSerializer(request.tenant).data)

    def patch(self, request):
        serializer = TenantProfileSerializer(request.tenant, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        tenant = serializer.save()
        return Response(TenantSerializer(tenant).data)

