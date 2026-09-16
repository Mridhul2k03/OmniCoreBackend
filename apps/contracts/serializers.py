from rest_framework import serializers
from apps.contracts.models import Tender, Proposal, Contract, ContractDocument, ContractAllocation, ContractTrip


class TenderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tender
        fields = ['id', 'tender_number', 'title', 'issuing_authority', 'submission_deadline', 'estimated_value', 'status', 'scope_of_work', 'created_at']
        read_only_fields = ['id', 'created_at']


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
