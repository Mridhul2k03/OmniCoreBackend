import csv
from django.http import HttpResponse
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from rest_framework.views import APIView
from rest_framework.response import Response
from apps.reports.selectors import PlatformDashboardSelector, TenantDashboardSelector
from apps.reports.report_selectors import REPORT_CATEGORIES, TenantReportSelector
from apps.reports.serializers import ReportRequestSerializer
from apps.core.permissions import IsPlatformAdmin, HasTenantAccess, HasPermission
from apps.core.exceptions import PermissionDeniedError
from apps.core.middleware import resolve_tenant_context
from apps.fleet.models import Vehicle
from apps.trips.models import Trip


@method_decorator(never_cache, name='dispatch')
class TenantReportAPIView(APIView):
    permission_classes = [HasTenantAccess, HasPermission]
    required_permission = 'reports.view'

    def _access_context(self, request):
        tenant, tenant_user = resolve_tenant_context(request)
        if request.user.is_superuser or getattr(request.user, 'is_platform_admin', False):
            return tenant, tenant_user, set()
        if not tenant or not tenant_user:
            raise PermissionDeniedError(detail='A valid tenant workspace is required.', code='TENANT_NOT_FOUND')
        if getattr(tenant_user, 'role', None) and tenant_user.role.code == 'TENANT_ADMIN':
            return tenant, tenant_user, {item['permission'] for item in REPORT_CATEGORIES}
        return tenant, tenant_user, set(tenant_user.get_all_permissions())


class ReportCategoriesView(TenantReportAPIView):
    def get(self, request):
        tenant, tenant_user, permissions = self._access_context(request)
        if request.user.is_superuser or getattr(request.user, 'is_platform_admin', False):
            allowed = REPORT_CATEGORIES
        elif getattr(tenant_user, 'role', None) and tenant_user.role.code == 'TENANT_ADMIN':
            allowed = REPORT_CATEGORIES
        else:
            allowed = [category for category in REPORT_CATEGORIES if category['permission'] in permissions]
        return Response({'categories': TenantReportSelector.get_categories({item['permission'] for item in allowed})})


class GenerateReportView(TenantReportAPIView):
    def get(self, request):
        serializer = ReportRequestSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        tenant, tenant_user, permissions = self._access_context(request)
        category = next(item for item in REPORT_CATEGORIES if item['id'] == data['category_id'])
        is_admin = bool(
            request.user.is_superuser or getattr(request.user, 'is_platform_admin', False) or
            (getattr(tenant_user, 'role', None) and tenant_user.role.code == 'TENANT_ADMIN')
        )
        if not is_admin and category['permission'] not in permissions:
            raise PermissionDeniedError(
                detail=f"Permission code '{category['permission']}' is required for this report.",
                code='MISSING_PERMISSION',
            )
        if not tenant:
            raise PermissionDeniedError(detail='A tenant workspace is required to generate reports.', code='TENANT_NOT_FOUND')

        result = TenantReportSelector.generate(
            tenant,
            data['category_id'],
            data['start_date'],
            data['end_date'],
        )
        return Response(result)


class PlatformDashboardView(APIView):
    """
    GET /api/v1/platform/dashboard/
    Global platform intelligence across all tenants, subscriptions, and verticals.
    """
    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        data = PlatformDashboardSelector.get_metrics()
        return Response(data)


class TenantDashboardView(APIView):
    """
    GET /api/v1/dashboard/
    Unified single-call operational dashboard for the active tenant.
    """
    permission_classes = [HasTenantAccess]

    def get(self, request):
        data = TenantDashboardSelector.get_metrics(request.tenant)
        return Response(data)


class ExportVehiclesCSVView(APIView):
    """
    GET /api/v1/reports/vehicles/csv/
    Exports tenant vehicle fleet as CSV.
    """
    permission_classes = [HasTenantAccess]

    def get(self, request):
        vehicles = Vehicle.objects.filter(tenant=request.tenant).select_related('category')
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="vehicles_report.csv"'

        writer = csv.writer(response)
        writer.writerow(['Registration Number', 'Category', 'Make', 'Model', 'Year', 'Status', 'Odometer', 'Fuel Type'])
        for v in vehicles:
            writer.writerow([
                v.registration_number,
                v.category.name if v.category else 'Uncategorized',
                v.make,
                v.model,
                v.year or '',
                v.status,
                v.odometer,
                v.fuel_type
            ])
        return response


class ExportTripsCSVView(APIView):
    """
    GET /api/v1/reports/trips/csv/
    Exports tenant trips as CSV.
    """
    permission_classes = [HasTenantAccess]

    def get(self, request):
        trips = Trip.objects.filter(tenant=request.tenant).select_related('customer', 'vehicle', 'driver')
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="trips_report.csv"'

        writer = csv.writer(response)
        writer.writerow(['Trip Number', 'Customer', 'Vehicle', 'Driver', 'Origin', 'Destination', 'Status', 'Distance (km)', 'Freight Charge'])
        for t in trips:
            writer.writerow([
                t.trip_number,
                t.customer.company_name,
                t.vehicle.registration_number if t.vehicle else '',
                t.driver.full_name if t.driver else '',
                t.origin,
                t.destination,
                t.status,
                t.distance_km,
                t.freight_charge
            ])
        return response
