import uuid
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import transaction
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from apps.core.viewsets import TenantModelViewSet
from apps.contracts.models import Tender, Proposal, Contract, ContractStatus, TenderStatus, ProposalStatus
from apps.contracts.serializers import TenderSerializer, ProposalSerializer, ContractSerializer, TenderAwardSerializer
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

    @action(detail=True, methods=['post'], url_path='award')
    def award(self, request, pk=None):
        tender = self.get_object()
        tenant = tender.tenant
        existing_contract = Contract.objects.filter(
            tenant=tenant, proposal__tender=tender,
        ).select_related('customer', 'proposal').first()
        if existing_contract:
            return Response({
                'tender': TenderSerializer(tender).data,
                'contract': ContractSerializer(existing_contract).data,
            }, status=status.HTTP_200_OK)
        if tender.status == TenderStatus.AWARDED:
            return Response({'detail': 'This tender is already awarded, but its contract record is missing.'}, status=status.HTTP_409_CONFLICT)
        if tender.status not in [TenderStatus.OPEN, TenderStatus.BID_SUBMITTED, TenderStatus.EVALUATION]:
            return Response({'detail': 'Only open, submitted, or evaluated tenders can be awarded.'}, status=status.HTTP_400_BAD_REQUEST)

        award_serializer = TenderAwardSerializer(data=request.data, context=self.get_serializer_context())
        award_serializer.is_valid(raise_exception=True)
        award = award_serializer.validated_data
        proposal_number = f"PRP-{timezone.localdate():%Y%m%d}-{uuid.uuid4().hex[:8].upper()}"

        with transaction.atomic():
            proposal = Proposal.objects.create(
                tenant=tenant, proposal_number=proposal_number, tender=tender,
                customer=award['customer'], quoted_amount=award['total_contract_value'],
                submission_date=timezone.localdate(), valid_until=award['end_date'],
                status=ProposalStatus.ACCEPTED,
                commercial_terms=f"Created from awarded tender {tender.tender_number}.",
            )
            contract_serializer = ContractSerializer(data={
                'title': tender.title,
                'customer': str(award['customer'].id),
                'start_date': award['start_date'],
                'end_date': award['end_date'],
                'total_contract_value': award['total_contract_value'],
                'minimum_monthly_commitment': award['minimum_monthly_commitment'],
                'payment_terms_days': award['payment_terms_days'],
                'status': ContractStatus.PENDING_APPROVAL,
            }, context=self.get_serializer_context())
            contract_serializer.is_valid(raise_exception=True)
            contract = contract_serializer.save(tenant=tenant, proposal=proposal)
            tender.status = TenderStatus.AWARDED
            tender.save(update_fields=['status', 'updated_at'])
            AuditService.record(
                action='TENDER_AWARDED', actor=request.user, tenant=tenant,
                target_type='Tender', target_id=str(tender.id),
                after_snapshot={
                    'status': tender.status, 'proposal_id': str(proposal.id),
                    'contract_id': str(contract.id), 'customer_id': str(award['customer'].id),
                },
            )

        return Response({
            'tender': TenderSerializer(tender).data,
            'contract': ContractSerializer(contract).data,
        }, status=status.HTTP_201_CREATED)


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
