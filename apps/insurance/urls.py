from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.insurance.views import (
    InsurancePolicyViewSet,
    InsuranceClaimViewSet,
    LegalDocumentViewSet,
    ComplianceRecordViewSet,
)

router = DefaultRouter()
router.register('policies', InsurancePolicyViewSet, basename='insurance_policies')
router.register('claims', InsuranceClaimViewSet, basename='insurance_claims')
router.register('legal-documents', LegalDocumentViewSet, basename='legal_documents')
router.register('compliance', ComplianceRecordViewSet, basename='compliance')

app_name = 'insurance'

urlpatterns = [
    path('insurance/', include(router.urls)),
]
