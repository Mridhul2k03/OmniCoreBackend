import uuid
from django.utils import timezone
from rest_framework import serializers
from apps.contracts.models import Tender, Proposal, Contract, ContractDocument, ContractAllocation, ContractTrip
from apps.crm.models import Customer
from apps.core.middleware import resolve_tenant_context


class TenderSerializer(serializers.ModelSerializer):
    tender_number = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = Tender
        fields = ['id', 'tender_number', 'title', 'issuing_authority', 'submission_deadline', 'estimated_value', 'status', 'scope_of_work', 'created_at']
        read_only_fields = ['id', 'created_at']

    def create(self, validated_data):
        number = str(validated_data.get('tender_number') or '').strip()
        if not number:
            number = f"TND-{timezone.localdate():%Y%m%d}-{uuid.uuid4().hex[:8].upper()}"
        validated_data['tender_number'] = number
        return super().create(validated_data)


class ProposalSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.company_name', read_only=True)

    class Meta:
        model = Proposal
        fields = ['id', 'proposal_number', 'tender', 'customer', 'customer_name', 'quoted_amount', 'submission_date', 'valid_until', 'status', 'commercial_terms', 'created_at']
        read_only_fields = ['id', 'created_at']


class ContractDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContractDocument
        fields = ['id', 'contract', 'document_title', 'document_type', 'file_path', 'uploaded_at']
        read_only_fields = ['id', 'uploaded_at']


class ContractAllocationSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='vehicle_category.name', read_only=True)

    class Meta:
        model = ContractAllocation
        fields = ['id', 'contract', 'vehicle_category', 'category_name', 'committed_vehicles', 'agreed_rate_per_km', 'agreed_monthly_fixed']
        read_only_fields = ['id']


class ContractSerializer(serializers.ModelSerializer):
    contract_number = serializers.CharField(required=False, allow_blank=True)
    customer_name = serializers.CharField(source='customer.company_name', read_only=True)
    documents = ContractDocumentSerializer(many=True, read_only=True)
    allocations = ContractAllocationSerializer(many=True, read_only=True)

    class Meta:
        model = Contract
        fields = [
            'id', 'contract_number', 'title', 'customer', 'customer_name',
            'proposal', 'start_date', 'end_date', 'total_contract_value',
            'minimum_monthly_commitment', 'payment_terms_days', 'status',
            'terms_and_conditions', 'documents', 'allocations', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']

    def create(self, validated_data):
        number = str(validated_data.get('contract_number') or '').strip()
        if not number:
            number = f"CTR-{timezone.localdate():%Y%m%d}-{uuid.uuid4().hex[:8].upper()}"
        validated_data['contract_number'] = number
        return super().create(validated_data)


class TenderAwardSerializer(serializers.Serializer):
    customer = serializers.PrimaryKeyRelatedField(queryset=Customer.objects.all())
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    total_contract_value = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=0)
    minimum_monthly_commitment = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0, required=False, default=0)
    payment_terms_days = serializers.IntegerField(min_value=0, required=False, default=30)

    def validate_customer(self, customer):
        tenant, _ = resolve_tenant_context(self.context['request'])
        if customer.tenant_id != tenant.id:
            raise serializers.ValidationError('Select a customer in this tenant workspace.')
        return customer

    def validate(self, attrs):
        if attrs['end_date'] < attrs['start_date']:
            raise serializers.ValidationError({'end_date': 'End date must be on or after the start date.'})
        return attrs
