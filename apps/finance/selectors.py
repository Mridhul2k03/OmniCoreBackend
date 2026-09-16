from decimal import Decimal
from django.db.models import Sum
from apps.finance.models import Invoice, Payment, Expense, FuelTransaction, TollTransaction


class FinanceSelector:
    @staticmethod
    def get_pnl_summary(tenant, start_date=None, end_date=None) -> dict:
        """
        Aggregates operational revenue and expenses for the tenant, avoiding N+1 queries.
        """
        payment_qs = Payment.objects.filter(tenant=tenant)
        expense_qs = Expense.objects.filter(tenant=tenant)
        fuel_qs = FuelTransaction.objects.filter(tenant=tenant)
        toll_qs = TollTransaction.objects.filter(tenant=tenant)
        invoice_qs = Invoice.objects.filter(tenant=tenant)

        if start_date:
            payment_qs = payment_qs.filter(payment_date__gte=start_date)
            expense_qs = expense_qs.filter(expense_date__gte=start_date)
            fuel_qs = fuel_qs.filter(transaction_date__gte=start_date)
            toll_qs = toll_qs.filter(transaction_time__gte=start_date)
            invoice_qs = invoice_qs.filter(issue_date__gte=start_date)

        if end_date:
            payment_qs = payment_qs.filter(payment_date__lte=end_date)
            expense_qs = expense_qs.filter(expense_date__lte=end_date)
            fuel_qs = fuel_qs.filter(transaction_date__lte=end_date)
            toll_qs = toll_qs.filter(transaction_time__lte=end_date)
            invoice_qs = invoice_qs.filter(issue_date__lte=end_date)

        total_billed = invoice_qs.aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
        total_collections = payment_qs.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        outstanding_receivables = invoice_qs.exclude(status='PAID').aggregate(total=Sum('balance_due'))['total'] or Decimal('0.00')

        total_fuel = fuel_qs.aggregate(total=Sum('total_cost'))['total'] or Decimal('0.00')
        total_tolls = toll_qs.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        total_operating_expenses = expense_qs.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

        total_expenses = total_fuel + total_tolls + total_operating_expenses
        net_operating_profit = total_collections - total_expenses
        profit_margin = 0.0
        if total_collections > 0:
            profit_margin = round((float(net_operating_profit) / float(total_collections)) * 100, 2)

        return {
            'total_billed_revenue': str(total_billed),
            'total_collections_cash': str(total_collections),
            'outstanding_receivables': str(outstanding_receivables),
            'expenses': {
                'fuel': str(total_fuel),
                'tolls': str(total_tolls),
                'operations_and_overhead': str(total_operating_expenses),
                'total_expenses': str(total_expenses),
            },
            'net_operating_profit': str(net_operating_profit),
            'profit_margin_percent': profit_margin
        }
