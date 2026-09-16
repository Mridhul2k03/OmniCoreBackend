from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.contracts.views import TenderViewSet, ProposalViewSet, ContractViewSet

router = DefaultRouter()
router.register('tenders', TenderViewSet, basename='tenders')
router.register('proposals', ProposalViewSet, basename='proposals')
router.register('', ContractViewSet, basename='contracts')

app_name = 'contracts'

urlpatterns = [
    path('contracts/', include(router.urls)),
]
