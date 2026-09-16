from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.finance.views import (
    InvoiceViewSet,
    PaymentViewSet,
    ExpenseViewSet,
    FuelTransactionViewSet,
    TollTransactionViewSet,
    CollectionViewSet,
    PnLSummaryView,
)

router = DefaultRouter()
router.register('invoices', InvoiceViewSet, basename='invoices')
router.register('payments', PaymentViewSet, basename='payments')
router.register('expenses', ExpenseViewSet, basename='expenses')
router.register('fuel', FuelTransactionViewSet, basename='fuel_transactions')
router.register('tolls', TollTransactionViewSet, basename='toll_transactions')
router.register('collections', CollectionViewSet, basename='collections')

app_name = 'finance'

urlpatterns = [
    path('finance/pnl/', PnLSummaryView.as_view(), name='finance_pnl'),
    path('finance/', include(router.urls)),
]
