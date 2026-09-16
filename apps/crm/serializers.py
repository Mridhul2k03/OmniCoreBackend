from rest_framework import serializers
from apps.crm.models import Customer, Lead, Inquiry, Quotation, Communication, FollowUp


class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = [
            'id', 'company_name', 'contact_person', 'email', 'phone',
            'address', 'tax_id', 'customer_type', 'credit_limit',
            'payment_terms_days', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class LeadSerializer(serializers.ModelSerializer):
    converted_customer_name = serializers.CharField(source='converted_customer.company_name', read_only=True)

    class Meta:
        model = Lead
        fields = [
            'id', 'name', 'company_name', 'email', 'phone', 'lead_source',
            'status', 'estimated_value', 'notes', 'converted_customer',
            'converted_customer_name', 'created_at'
        ]
        read_only_fields = ['id', 'converted_customer', 'created_at']


class InquirySerializer(serializers.ModelSerializer):
    class Meta:
        model = Inquiry
        fields = [
            'id', 'customer', 'lead', 'origin', 'destination', 'cargo_type',
            'estimated_weight_kg', 'inquiry_date', 'status', 'notes'
        ]
        read_only_fields = ['id', 'inquiry_date']


class QuotationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Quotation
        fields = [
            'id', 'quotation_number', 'customer', 'lead', 'subtotal',
            'tax_amount', 'total_amount', 'valid_until', 'status',
            'terms_and_conditions', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class CommunicationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Communication
        fields = ['id', 'customer', 'lead', 'channel', 'direction', 'summary', 'details', 'timestamp']
        read_only_fields = ['id', 'timestamp']


class FollowUpSerializer(serializers.ModelSerializer):
    class Meta:
        model = FollowUp
        fields = ['id', 'customer', 'lead', 'due_date', 'notes', 'is_completed']
        read_only_fields = ['id']
