from decimal import Decimal

from django.db.models import Q, Sum, DecimalField
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.fleet.models import Vehicle
from apps.finance.models import Invoice, InvoiceStatus, FuelTransaction
from apps.maintenance.models import MaintenanceRecord
from apps.trips.models import Trip, TripExpense


REPORT_CATEGORIES = [
    {
        'id': 'fleet',
        'name': 'Fleet Activity & Fuel',
        'description': 'Current fleet status with distance, fuel volume, and fuel spend recorded in the selected period.',
        'icon': 'Truck',
        'permission': 'vehicle.view',
        'fields': ['Vehicle', 'Make / Model', 'Status', 'Odometer (km)', 'Distance (km)', 'Fuel (L)', 'Fuel Spend'],
    },
    {
        'id': 'trips',
        'name': 'Trips & Dispatch Revenue',
        'description': 'Trips scheduled or started in the selected period with recorded freight charges and direct trip expenses.',
        'icon': 'Navigation',
        'permission': 'trip.view',
        'fields': ['Trip', 'Customer', 'Origin', 'Destination', 'Vehicle', 'Status', 'Distance (km)', 'Freight Charge', 'Trip Expenses', 'Net Margin'],
    },
    {
        'id': 'maintenance',
        'name': 'Workshop & Maintenance Spend',
        'description': 'Maintenance records by service date, vehicle, service type, workshop, and recorded cost.',
        'icon': 'Wrench',
        'permission': 'maintenance.view',
        'fields': ['Date', 'Vehicle', 'Service Type', 'Service Center', 'Odometer (km)', 'Cost', 'Notes'],
    },
    {
        'id': 'finance',
        'name': 'Financial Invoices & Receivables',
        'description': 'Invoices issued in the selected period with paid balances and current overdue amounts.',
        'icon': 'DollarSign',
        'permission': 'finance.view',
        'fields': ['Invoice', 'Customer', 'Issue Date', 'Due Date', 'Total', 'Paid', 'Balance Due', 'Days Overdue', 'Status'],
    },
    {
        'id': 'cold_chain',
        'name': 'Cold-Chain Integrity',
        'description': 'Temperature excursions and compliance data. A temperature telemetry source is not connected yet.',
        'icon': 'Snowflake',
        'permission': 'trip.view',
        'available': False,
        'fields': ['Trip', 'Reefer Unit', 'Target Temp', 'Min Temp', 'Max Temp', 'Breach Incidents', 'SLA Result'],
    },
]


def _money(value):
    return str(value if value is not None else Decimal('0.00'))


class TenantReportSelector:
    @classmethod
    def get_categories(cls, permission_codes):
        return [
            {key: value for key, value in category.items() if key != 'permission'}
            for category in REPORT_CATEGORIES
            if category['permission'] in permission_codes
        ]

    @classmethod
    def generate(cls, tenant, category_id, start_date, end_date):
        category = next(item for item in REPORT_CATEGORIES if item['id'] == category_id)
        if category_id == 'fleet':
            rows, summary = cls._fleet(tenant, start_date, end_date)
        elif category_id == 'trips':
            rows, summary = cls._trips(tenant, start_date, end_date)
        elif category_id == 'maintenance':
            rows, summary = cls._maintenance(tenant, start_date, end_date)
        elif category_id == 'finance':
            rows, summary = cls._finance(tenant, start_date, end_date)
        else:
            rows = []
            summary = [
                {'label': 'Status', 'value': 'Unavailable'},
                {'label': 'Records', 'value': 0},
            ]

        return {
            'title': category['name'],
            'category': category['name'],
            'generated_at': timezone.now().isoformat(),
            'period': {'start_date': start_date.isoformat(), 'end_date': end_date.isoformat()},
            'available': category.get('available', True),
            'notice': None if category.get('available', True) else 'No temperature telemetry source is connected, so this report has no records.',
            'columns': category['fields'],
            'rows': rows,
            'summary': summary,
            'truncated': False,
        }

    @staticmethod
    def _fleet(tenant, start_date, end_date):
        fuel_by_vehicle = {
            item['vehicle_id']: item
            for item in FuelTransaction.objects.filter(
                tenant=tenant, transaction_date__date__range=(start_date, end_date)
            ).values('vehicle_id').annotate(
                liters=Coalesce(Sum('fuel_liters'), Decimal('0.00')),
                spend=Coalesce(Sum('total_cost'), Decimal('0.00')),
            )
        }
        trip_by_vehicle = {
            item['vehicle_id']: item['distance']
            for item in Trip.objects.filter(tenant=tenant, vehicle__isnull=False).filter(
                Q(actual_start__date__range=(start_date, end_date)) |
                Q(actual_start__isnull=True, scheduled_start__date__range=(start_date, end_date))
            ).values('vehicle_id').annotate(distance=Coalesce(Sum('distance_km'), Decimal('0.00')))
        }
        vehicles = Vehicle.objects.filter(tenant=tenant).select_related('category').order_by('registration_number')
        rows = []
        for vehicle in vehicles:
            fuel = fuel_by_vehicle.get(vehicle.id, {})
            rows.append({
                'Vehicle': vehicle.registration_number,
                'Make / Model': f'{vehicle.make} {vehicle.model}'.strip(),
                'Status': vehicle.status,
                'Odometer (km)': _money(vehicle.odometer),
                'Distance (km)': _money(trip_by_vehicle.get(vehicle.id, Decimal('0.00'))),
                'Fuel (L)': _money(fuel.get('liters', Decimal('0.00'))),
                'Fuel Spend': _money(fuel.get('spend', Decimal('0.00'))),
            })
        summary = [
            {'label': 'Vehicles', 'value': len(rows)},
            {'label': 'Available', 'value': sum(1 for row in rows if row['Status'] == 'AVAILABLE')},
            {'label': 'Distance in Period (km)', 'value': _money(sum((Decimal(row['Distance (km)']) for row in rows), Decimal('0.00')))},
            {'label': 'Fuel Spend in Period', 'value': _money(sum((Decimal(row['Fuel Spend']) for row in rows), Decimal('0.00')))},
        ]
        return rows, summary

    @staticmethod
    def _trips(tenant, start_date, end_date):
        period_filter = (
            Q(actual_start__date__range=(start_date, end_date)) |
            Q(actual_start__isnull=True, scheduled_start__date__range=(start_date, end_date)) |
            Q(actual_start__isnull=True, scheduled_start__isnull=True, created_at__date__range=(start_date, end_date))
        )
        trips = Trip.objects.filter(tenant=tenant).filter(period_filter).select_related(
            'customer', 'vehicle'
        ).annotate(
            trip_expenses=Coalesce(
                Sum('expenses__amount'), Decimal('0.00'), output_field=DecimalField()
            )
        ).order_by('-created_at')

        rows = []
        for trip in trips:
            expenses = trip.trip_expenses or Decimal('0.00')
            charge = trip.freight_charge or Decimal('0.00')
            rows.append({
                'Trip': trip.trip_number,
                'Customer': trip.customer.company_name,
                'Origin': trip.origin,
                'Destination': trip.destination,
                'Vehicle': trip.vehicle.registration_number if trip.vehicle else '',
                'Status': trip.status,
                'Distance (km)': _money(trip.distance_km),
                'Freight Charge': _money(charge),
                'Trip Expenses': _money(expenses),
                'Net Margin': _money(charge - expenses),
            })
        total_charge = sum((trip.freight_charge or Decimal('0.00') for trip in trips), Decimal('0.00'))
        total_expenses = sum((trip.trip_expenses or Decimal('0.00') for trip in trips), Decimal('0.00'))
        summary = [
            {'label': 'Trips', 'value': len(rows)},
            {'label': 'Completed', 'value': sum(1 for trip in trips if trip.status in ('COMPLETED', 'BILLING_READY'))},
            {'label': 'Freight Charges', 'value': _money(total_charge)},
            {'label': 'Net After Trip Expenses', 'value': _money(total_charge - total_expenses)},
        ]
        return rows, summary

    @staticmethod
    def _maintenance(tenant, start_date, end_date):
        records = MaintenanceRecord.objects.filter(
            tenant=tenant, performed_date__range=(start_date, end_date)
        ).select_related('vehicle').order_by('-performed_date')
        rows = [{
            'Date': record.performed_date.isoformat(),
            'Vehicle': record.vehicle.registration_number,
            'Service Type': record.service_type,
            'Service Center': record.service_center,
            'Odometer (km)': _money(record.odometer_reading),
            'Cost': _money(record.cost),
            'Notes': record.notes,
        } for record in records]
        total_cost = sum((record.cost or Decimal('0.00') for record in records), Decimal('0.00'))
        summary = [
            {'label': 'Service Records', 'value': len(rows)},
            {'label': 'Total Spend', 'value': _money(total_cost)},
            {'label': 'Average Cost', 'value': _money(total_cost / len(rows) if rows else Decimal('0.00'))},
        ]
        return rows, summary

    @staticmethod
    def _finance(tenant, start_date, end_date):
        today = timezone.localdate()
        invoices = Invoice.objects.filter(
            tenant=tenant,
            issue_date__range=(start_date, end_date),
        ).exclude(status=InvoiceStatus.CANCELLED).select_related('customer').order_by('-issue_date')
        rows = []
        for invoice in invoices:
            balance = invoice.balance_due or Decimal('0.00')
            days_overdue = max((today - invoice.due_date).days, 0) if balance > 0 else 0
            rows.append({
                'Invoice': invoice.invoice_number,
                'Customer': invoice.customer.company_name,
                'Issue Date': invoice.issue_date.isoformat(),
                'Due Date': invoice.due_date.isoformat(),
                'Total': _money(invoice.total_amount),
                'Paid': _money(invoice.paid_amount),
                'Balance Due': _money(balance),
                'Days Overdue': days_overdue,
                'Status': invoice.status,
            })
        invoiced = sum((invoice.total_amount or Decimal('0.00') for invoice in invoices), Decimal('0.00'))
        paid = sum((invoice.paid_amount or Decimal('0.00') for invoice in invoices), Decimal('0.00'))
        outstanding = sum((invoice.balance_due or Decimal('0.00') for invoice in invoices), Decimal('0.00'))
        overdue = sum((invoice.balance_due or Decimal('0.00') for invoice in invoices if invoice.due_date < today), Decimal('0.00'))
        summary = [
            {'label': 'Invoices', 'value': len(rows)},
            {'label': 'Invoiced', 'value': _money(invoiced)},
            {'label': 'Paid', 'value': _money(paid)},
            {'label': 'Outstanding', 'value': _money(outstanding)},
            {'label': 'Overdue', 'value': _money(overdue)},
        ]
        return rows, summary
