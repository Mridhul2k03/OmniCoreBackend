from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from apps.core.viewsets import TenantModelViewSet
from apps.crm.models import Customer, Lead, Inquiry, Quotation, Communication, FollowUp
from apps.crm.serializers import (
    CustomerSerializer,
    LeadSerializer,
    InquirySerializer,
    QuotationSerializer,
    CommunicationSerializer,
    FollowUpSerializer,
)
from apps.crm.services import CustomerService
from apps.core.exceptions import BusinessValidationError


class CustomerViewSet(TenantModelViewSet):
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer
    required_permission = 'crm.view'
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['customer_type', 'is_active']
    search_fields = ['company_name', 'contact_person', 'email', 'phone']
    ordering_fields = ['created_at', 'company_name']


class LeadViewSet(TenantModelViewSet):
    queryset = Lead.objects.all().select_related('converted_customer')
    serializer_class = LeadSerializer
    required_permission = 'crm.view'
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'lead_source']
    search_fields = ['name', 'company_name', 'email', 'phone']
    ordering_fields = ['created_at', 'estimated_value']

    @action(detail=True, methods=['post'])
    def convert(self, request, pk=None):
        lead = self.get_object()
        credit_limit = request.data.get('credit_limit', 0)
        payment_terms = request.data.get('payment_terms_days', 30)
        customer = CustomerService.convert_lead_to_customer(
            lead=lead,
            credit_limit=credit_limit,
            payment_terms_days=payment_terms,
            actor=request.user
        )
        return Response({
            'message': f"Lead successfully converted into Customer '{customer.company_name}'.",
            'customer_id': str(customer.id)
        }, status=status.HTTP_201_CREATED)


class InquiryViewSet(TenantModelViewSet):
    queryset = Inquiry.objects.all().select_related('customer', 'lead')
    serializer_class = InquirySerializer
    required_permission = 'crm.view'
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['status', 'cargo_type', 'customer']
    search_fields = ['origin', 'destination']


class QuotationViewSet(TenantModelViewSet):
    queryset = Quotation.objects.all().select_related('customer', 'lead')
    serializer_class = QuotationSerializer
    required_permission = 'crm.view'
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'customer']
    search_fields = ['quotation_number']
    ordering_fields = ['created_at', 'total_amount']


class CommunicationViewSet(TenantModelViewSet):
    queryset = Communication.objects.all().select_related('customer', 'lead')
    serializer_class = CommunicationSerializer
    required_permission = 'crm.view'


class FollowUpViewSet(TenantModelViewSet):
    queryset = FollowUp.objects.all().select_related('customer', 'lead')
    serializer_class = FollowUpSerializer
    required_permission = 'crm.view'
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['is_completed', 'due_date']
