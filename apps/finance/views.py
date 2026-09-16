from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from apps.core.viewsets import TenantModelViewSet
from apps.finance.models import (
    Invoice,
    Payment,
    Expense,
    FuelTransaction,
    TollTransaction,
    Collection,
    InvoiceStatus,
)
from apps.finance.serializers import (
    InvoiceSerializer,
    PaymentSerializer,
    ExpenseSerializer,
    FuelTransactionSerializer,
    TollTransactionSerializer,
    CollectionSerializer,
)
from apps.finance.services import FinanceService
from apps.finance.selectors import FinanceSelector
from apps.core.permissions import HasTenantAccess, HasPermission
from apps.core.exceptions import BusinessValidationError


class InvoiceViewSet(TenantModelViewSet):
    queryset = Invoice.objects.all().select_related('customer').prefetch_related('items', 'payments')
    serializer_class = InvoiceSerializer
    required_permission = 'finance.view'
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'customer']
    search_fields = ['invoice_number']
    ordering_fields = ['issue_date', 'due_date', 'total_amount']

    @action(detail=True, methods=['post'])
    def record_payment(self, request, pk=None):
        invoice = self.get_object()
        amount = request.data.get('amount')
        if not amount:
            raise BusinessValidationError("A valid 'amount' is required.")

        payment = FinanceService.record_payment(
            invoice=invoice,
            amount=amount,
            payment_method=request.data.get('payment_method', 'BANK_TRANSFER'),
            reference_number=request.data.get('reference_number', ''),
            idempotency_key=request.data.get('idempotency_key'),
            notes=request.data.get('notes', ''),
            actor=request.user
        )

        return Response({
            'message': 'Payment recorded successfully.',
            'payment_id': str(payment.id),
            'payment_number': payment.payment_number,
            'new_balance_due': str(invoice.balance_due),
            'invoice_status': invoice.status
        })


class PaymentViewSet(TenantModelViewSet):
    queryset = Payment.objects.all().select_related('invoice')
    serializer_class = PaymentSerializer
    required_permission = 'finance.view'
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['payment_method', 'invoice']
    ordering_fields = ['payment_date', 'amount']


class ExpenseViewSet(TenantModelViewSet):
    queryset = Expense.objects.all()
    serializer_class = ExpenseSerializer
    required_permission = 'finance.view'
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['category']
    search_fields = ['expense_number', 'description']
    ordering_fields = ['expense_date', 'amount']


class FuelTransactionViewSet(TenantModelViewSet):
    queryset = FuelTransaction.objects.all().select_related('vehicle', 'driver')
    serializer_class = FuelTransactionSerializer
    required_permission = 'finance.view'
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['vehicle', 'driver']
    ordering_fields = ['transaction_date', 'total_cost']


class TollTransactionViewSet(TenantModelViewSet):
    queryset = TollTransaction.objects.all().select_related('vehicle')
    serializer_class = TollTransactionSerializer
    required_permission = 'finance.view'
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['vehicle']
    ordering_fields = ['transaction_time', 'amount']


class CollectionViewSet(TenantModelViewSet):
    queryset = Collection.objects.all().select_related('customer')
    serializer_class = CollectionSerializer
    required_permission = 'finance.view'


class PnLSummaryView(APIView):
    """
    GET /api/v1/finance/pnl/
    Returns aggregated P&L, collections, and expense breakdown.
    """
    permission_classes = [HasTenantAccess, HasPermission]
    required_permission = 'pnl.view'

    def get(self, request):
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        data = FinanceSelector.get_pnl_summary(request.tenant, start_date=start_date, end_date=end_date)
        return Response(data)
