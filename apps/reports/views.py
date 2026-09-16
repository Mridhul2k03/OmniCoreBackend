import csv
from django.http import HttpResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from apps.reports.selectors import PlatformDashboardSelector, TenantDashboardSelector
from apps.core.permissions import IsPlatformAdmin, HasTenantAccess
from apps.fleet.models import Vehicle
from apps.trips.models import Trip


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
