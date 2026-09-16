from decimal import Decimal
from django.db import models
from django.db.models import Count, Sum, Q
from django.utils import timezone
from apps.tenants.models import Tenant, TenantUser
from apps.subscriptions.models import Subscription, Package
from apps.fleet.models import Vehicle, VehicleStatus, VehicleDocument
from apps.drivers.models import Driver, DriverStatus
from apps.trips.models import Trip, TripStatus
from apps.maintenance.models import RepairOrder, MaintenanceSchedule
from apps.warehouse.models import SparePart
from apps.finance.models import Invoice, Payment, FuelTransaction, TollTransaction


class PlatformDashboardSelector:
    @staticmethod
    def get_metrics() -> dict:
        total_tenants = Tenant.objects.count()
        active_tenants = Tenant.objects.filter(status='ACTIVE').count()
        trial_tenants = Tenant.objects.filter(status='TRIAL').count()
        suspended_tenants = Tenant.objects.filter(status='SUSPENDED').count()

        package_dist = list(
            Tenant.objects.values('package__code', 'package__name')
            .annotate(count=Count('id'))
            .order_by('-count')
        )

        vertical_dist = list(
            Tenant.objects.values('verticals__name')
            .annotate(count=Count('id'))
            .order_by('-count')
        )

        total_users = TenantUser.objects.values('user').distinct().count()

        return {
            'tenants': {
                'total': total_tenants,
                'active': active_tenants,
                'trial': trial_tenants,
                'suspended': suspended_tenants,
            },
            'total_users': total_users,
            'package_distribution': package_dist,
            'vertical_distribution': vertical_dist,
        }


class TenantDashboardSelector:
    @staticmethod
    def get_metrics(tenant) -> dict:
        now = timezone.now()
        today = now.date()
        month_start = today.replace(day=1)

        # Fleet metrics
        total_vehicles = Vehicle.objects.filter(tenant=tenant).count()
        available_vehicles = Vehicle.objects.filter(tenant=tenant, status=VehicleStatus.AVAILABLE).count()
        on_trip_vehicles = Vehicle.objects.filter(tenant=tenant, status=VehicleStatus.ON_TRIP).count()
        maintenance_vehicles = Vehicle.objects.filter(tenant=tenant, status=VehicleStatus.MAINTENANCE).count()
        utilization_rate = round((on_trip_vehicles / total_vehicles * 100), 1) if total_vehicles > 0 else 0.0

        # Driver metrics
        total_drivers = Driver.objects.filter(tenant=tenant).count()
        available_drivers = Driver.objects.filter(tenant=tenant, status=DriverStatus.AVAILABLE).count()
        on_trip_drivers = Driver.objects.filter(tenant=tenant, status=DriverStatus.ON_TRIP).count()

        # Trip metrics
        active_trips = Trip.objects.filter(
            tenant=tenant,
            status__in=[TripStatus.DISPATCHED, TripStatus.STARTED, TripStatus.IN_PROGRESS]
        ).count()
        completed_trips_month = Trip.objects.filter(
            tenant=tenant,
            status__in=[TripStatus.COMPLETED, TripStatus.BILLING_READY],
            actual_end__date__gte=month_start
        ).count()

        # Warehouse & Inventory metrics
        low_inventory_count = SparePart.objects.filter(
            tenant=tenant,
            current_stock__lte=models.F('reorder_level')
        ).count()

        # Maintenance metrics
        open_repairs = RepairOrder.objects.filter(
            tenant=tenant,
            status__in=['OPEN', 'IN_PROGRESS']
        ).count()

        # Document Expiries in next 15 days
        expiring_docs_count = VehicleDocument.objects.filter(
            tenant=tenant,
            expiry_date__lte=today + timezone.timedelta(days=15),
            expiry_date__gte=today
        ).count()

        # Financial aggregations
        revenue_month = Invoice.objects.filter(
            tenant=tenant,
            issue_date__gte=month_start
        ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')

        collections_month = Payment.objects.filter(
            tenant=tenant,
            payment_date__gte=month_start
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

        outstanding_receivables = Invoice.objects.filter(
            tenant=tenant
        ).exclude(status='PAID').aggregate(total=Sum('balance_due'))['total'] or Decimal('0.00')

        fuel_month = FuelTransaction.objects.filter(
            tenant=tenant,
            transaction_date__date__gte=month_start
        ).aggregate(total=Sum('total_cost'))['total'] or Decimal('0.00')

        tolls_month = TollTransaction.objects.filter(
            tenant=tenant,
            transaction_time__date__gte=month_start
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

        return {
            'fleet': {
                'total_vehicles': total_vehicles,
                'available_vehicles': available_vehicles,
                'on_trip_vehicles': on_trip_vehicles,
                'maintenance_vehicles': maintenance_vehicles,
                'utilization_rate_percent': utilization_rate,
            },
            'drivers': {
                'total_drivers': total_drivers,
                'available_drivers': available_drivers,
                'on_trip_drivers': on_trip_drivers,
            },
            'trips': {
                'active_trips': active_trips,
                'completed_trips_this_month': completed_trips_month,
            },
            'alerts': {
                'low_inventory_skus': low_inventory_count,
                'open_repair_orders': open_repairs,
                'expiring_documents_soon': expiring_docs_count,
            },
            'finance_month_to_date': {
                'revenue_billed': str(revenue_month),
                'collections_cash': str(collections_month),
                'outstanding_receivables': str(outstanding_receivables),
                'fuel_spend': str(fuel_month),
                'toll_spend': str(tolls_month),
            }
        }
