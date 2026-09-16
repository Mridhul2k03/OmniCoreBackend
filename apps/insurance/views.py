from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from apps.core.viewsets import TenantModelViewSet
from apps.insurance.models import InsurancePolicy, InsuranceClaim, LegalDocument, ComplianceRecord
from apps.insurance.serializers import (
    InsurancePolicySerializer,
    InsuranceClaimSerializer,
    LegalDocumentSerializer,
    ComplianceRecordSerializer,
)


class InsurancePolicyViewSet(TenantModelViewSet):
    queryset = InsurancePolicy.objects.all().select_related('vehicle')
    serializer_class = InsurancePolicySerializer
    required_permission = 'insurance.view'
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'policy_type', 'vehicle']
    search_fields = ['policy_number', 'provider_name']
    ordering_fields = ['end_date', 'premium_amount']


class InsuranceClaimViewSet(TenantModelViewSet):
    queryset = InsuranceClaim.objects.all().select_related('policy')
    serializer_class = InsuranceClaimSerializer
    required_permission = 'insurance.view'
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['status', 'policy']
    search_fields = ['claim_number']


class LegalDocumentViewSet(TenantModelViewSet):
    queryset = LegalDocument.objects.all()
    serializer_class = LegalDocumentSerializer
    required_permission = 'insurance.view'
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['status', 'document_type']
    search_fields = ['title', 'reference_number']


class ComplianceRecordViewSet(TenantModelViewSet):
    queryset = ComplianceRecord.objects.all()
    serializer_class = ComplianceRecordSerializer
    required_permission = 'insurance.view'
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['compliance_status']
    ordering_fields = ['next_due_date']
