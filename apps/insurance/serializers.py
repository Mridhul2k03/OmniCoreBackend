from rest_framework import serializers
from apps.insurance.models import InsurancePolicy, InsuranceClaim, LegalDocument, ComplianceRecord


class InsurancePolicySerializer(serializers.ModelSerializer):
    vehicle_reg = serializers.CharField(source='vehicle.registration_number', read_only=True)

    class Meta:
        model = InsurancePolicy
        fields = [
            'id', 'policy_number', 'provider_name', 'policy_type',
            'vehicle', 'vehicle_reg', 'start_date', 'end_date',
            'premium_amount', 'coverage_amount', 'status', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class InsuranceClaimSerializer(serializers.ModelSerializer):
    policy_number = serializers.CharField(source='policy.policy_number', read_only=True)

    class Meta:
        model = InsuranceClaim
        fields = [
            'id', 'claim_number', 'policy', 'policy_number', 'incident_date',
            'claim_amount', 'approved_amount', 'status', 'surveyor_name', 'notes', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class LegalDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = LegalDocument
        fields = ['id', 'title', 'document_type', 'reference_number', 'effective_date', 'expiry_date', 'file_path', 'status', 'created_at']
        read_only_fields = ['id', 'created_at']


class ComplianceRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = ComplianceRecord
        fields = ['id', 'regulation_name', 'authority', 'compliance_status', 'audit_date', 'next_due_date', 'notes', 'created_at']
        read_only_fields = ['id', 'created_at']
