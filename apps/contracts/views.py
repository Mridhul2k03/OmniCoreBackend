from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from apps.core.viewsets import TenantModelViewSet
from apps.contracts.models import Tender, Proposal, Contract, ContractStatus
from apps.contracts.serializers import TenderSerializer, ProposalSerializer, ContractSerializer
from apps.audit.services import AuditService


class TenderViewSet(TenantModelViewSet):
    queryset = Tender.objects.all()
    serializer_class = TenderSerializer
    required_feature = 'contracts'
    required_permission = 'contract.view'
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status']
    search_fields = ['tender_number', 'title', 'issuing_authority']
    ordering_fields = ['submission_deadline', 'created_at']


class ProposalViewSet(TenantModelViewSet):
    queryset = Proposal.objects.all().select_related('customer', 'tender')
    serializer_class = ProposalSerializer
    required_feature = 'contracts'
    required_permission = 'contract.view'
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['status', 'customer']
    search_fields = ['proposal_number']


class ContractViewSet(TenantModelViewSet):
    queryset = Contract.objects.all().select_related('customer', 'proposal').prefetch_related('documents', 'allocations')
    serializer_class = ContractSerializer
    required_feature = 'contracts'
    required_permission = 'contract.view'
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'customer']
    search_fields = ['contract_number', 'title']
    ordering_fields = ['start_date', 'end_date', 'total_contract_value']

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        contract = self.get_object()
        contract.status = ContractStatus.ACTIVE
        contract.save(update_fields=['status'])

        AuditService.record(
            action='CONTRACT_APPROVED',
            actor=request.user,
            tenant=request.tenant,
            target_type='Contract',
            target_id=str(contract.id),
            after_snapshot={'status': contract.status}
        )
        return Response({'message': f"Contract {contract.contract_number} has been approved and marked ACTIVE."})
