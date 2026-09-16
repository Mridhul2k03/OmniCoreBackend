from rest_framework import serializers
from apps.courier.models import (
    Hub, CourierAgent, Shipment, ShipmentParcel, PickupLocation,
    ShipmentPickup, SortingRecord, TrackingEvent, Delivery,
    DeliveryAttempt, ProofOfDelivery, CourierCommission, CourierExpense, CourierPayout
)
from apps.courier.services import generate_awb


class HubSerializer(serializers.ModelSerializer):
    class Meta:
        model = Hub
        fields = [
            'id', 'name', 'code', 'address', 'city', 'state',
            'postal_code', 'contact_phone', 'contact_email',
            'status', 'capacity_sqft', 'manager', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class CourierAgentSerializer(serializers.ModelSerializer):
    display_name = serializers.ReadOnlyField()

    class Meta:
        model = CourierAgent
        fields = [
            'id', 'agent_code', 'driver', 'user', 'vehicle', 'service_area',
            'status', 'commission_rate_per_delivery', 'current_hub',
            'display_name', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'display_name', 'created_at', 'updated_at']


class ShipmentParcelSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShipmentParcel
        fields = ['id', 'barcode', 'weight_kg', 'dimensions', 'description']
        read_only_fields = ['id']


class PickupLocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = PickupLocation
        fields = ['id', 'name', 'contact_person', 'contact_phone', 'address', 'city', 'postal_code', 'notes']
        read_only_fields = ['id']


class ShipmentPickupSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShipmentPickup
        fields = [
            'id', 'shipment', 'pickup_location', 'sequence', 'address',
            'contact_name', 'contact_phone', 'scheduled_time', 'assigned_agent',
            'status', 'actual_pickup_time', 'failure_reason', 'notes', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class TrackingEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = TrackingEvent
        fields = ['id', 'event_type', 'status', 'timestamp', 'location', 'actor', 'description', 'metadata']
        read_only_fields = ['id', 'timestamp']


class SortingRecordSerializer(serializers.ModelSerializer):
    source_hub_name = serializers.ReadOnlyField(source='source_hub.name')
    destination_hub_name = serializers.ReadOnlyField(source='destination_hub.name')

    class Meta:
        model = SortingRecord
        fields = [
            'id', 'shipment', 'source_hub', 'source_hub_name', 'destination_hub',
            'destination_hub_name', 'sorting_category', 'operator', 'status',
            'timestamp', 'notes'
        ]
        read_only_fields = ['id', 'timestamp', 'source_hub_name', 'destination_hub_name']


class ProofOfDeliverySerializer(serializers.ModelSerializer):
    class Meta:
        model = ProofOfDelivery
        fields = [
            'id', 'delivery', 'verification_method', 'otp_verified',
            'digital_signature_file', 'recipient_name', 'delivery_timestamp',
            'agent', 'notes', 'attachment_file'
        ]
        read_only_fields = ['id', 'otp_verified', 'delivery_timestamp']


class DeliveryAttemptSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeliveryAttempt
        fields = ['id', 'attempt_number', 'timestamp', 'reason', 'notes']
        read_only_fields = ['id', 'timestamp']


class DeliverySerializer(serializers.ModelSerializer):
    pod = ProofOfDeliverySerializer(read_only=True)
    attempts = DeliveryAttemptSerializer(many=True, read_only=True)
    shipment_awb = serializers.ReadOnlyField(source='shipment.awb_number')

    class Meta:
        model = Delivery
        fields = [
            'id', 'shipment', 'shipment_awb', 'invoice', 'agent', 'scheduled_delivery',
            'delivery_status', 'attempt_count', 'delivery_address', 'recipient_name',
            'recipient_phone', 'notes', 'pod', 'attempts', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'shipment_awb', 'attempt_count', 'created_at', 'updated_at']


class ShipmentSerializer(serializers.ModelSerializer):
    parcels = ShipmentParcelSerializer(many=True, required=False)
    pickups = ShipmentPickupSerializer(many=True, required=False)
    tracking_events = TrackingEventSerializer(many=True, read_only=True)
    delivery_task = DeliverySerializer(read_only=True)

    class Meta:
        model = Shipment
        fields = [
            'id', 'awb_number', 'customer', 'invoice', 'sender_name', 'sender_phone',
            'sender_email', 'sender_address', 'sender_city', 'sender_postal_code',
            'receiver_name', 'receiver_phone', 'receiver_email', 'delivery_address',
            'delivery_city', 'delivery_postal_code', 'service_type', 'weight_kg',
            'dimensions', 'parcel_count', 'declared_value', 'shipping_cost',
            'origin_hub', 'current_hub', 'destination_hub', 'assigned_agent',
            'status', 'expected_delivery', 'notes', 'parcels', 'pickups',
            'tracking_events', 'delivery_task', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'awb_number', 'status', 'created_at', 'updated_at']

    def create(self, validated_data):
        parcels_data = validated_data.pop('parcels', [])
        pickups_data = validated_data.pop('pickups', [])
        validated_data['awb_number'] = generate_awb()
        
        shipment = Shipment.objects.create(**validated_data)
        
        for p in parcels_data:
            ShipmentParcel.objects.create(tenant=shipment.tenant, shipment=shipment, **p)
            
        for pick in pickups_data:
            ShipmentPickup.objects.create(tenant=shipment.tenant, shipment=shipment, **pick)
            
        # Initial tracking event
        TrackingEvent.objects.create(
            tenant=shipment.tenant,
            shipment=shipment,
            event_type="BOOKED",
            status=shipment.status,
            location=shipment.sender_city,
            description="Shipment booked and AWB generated."
        )
        return shipment


class CourierCommissionSerializer(serializers.ModelSerializer):
    agent_name = serializers.ReadOnlyField(source='agent.display_name')

    class Meta:
        model = CourierCommission
        fields = ['id', 'agent', 'agent_name', 'delivery', 'shipment', 'commission_amount', 'date', 'status']
        read_only_fields = ['id', 'agent_name', 'date']


class CourierExpenseSerializer(serializers.ModelSerializer):
    class Meta:
        model = CourierExpense
        fields = ['id', 'agent', 'expense_type', 'amount', 'date', 'notes', 'is_approved']
        read_only_fields = ['id', 'date']


class CourierPayoutSerializer(serializers.ModelSerializer):
    agent_name = serializers.ReadOnlyField(source='agent.display_name')

    class Meta:
        model = CourierPayout
        fields = [
            'id', 'payout_number', 'agent', 'agent_name', 'gross_amount',
            'total_deductions', 'net_payable', 'period_start', 'period_end',
            'status', 'idempotency_key', 'paid_at', 'notes', 'created_at'
        ]
        read_only_fields = ['id', 'payout_number', 'agent_name', 'created_at']


class PublicSafeTrackingEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = TrackingEvent
        fields = ['event_type', 'status', 'timestamp', 'location', 'description']


class PublicTrackingSerializer(serializers.ModelSerializer):
    """
    Strictly sanitized public tracking serializer. Never leaks PII, financial details, or internal tenant notes.
    """
    events = PublicSafeTrackingEventSerializer(source='tracking_events', many=True, read_only=True)
    sender_city = serializers.CharField(read_only=True)
    delivery_city = serializers.CharField(read_only=True)
    masked_receiver = serializers.SerializerMethodField()

    class Meta:
        model = Shipment
        fields = [
            'awb_number', 'status', 'service_type', 'sender_city',
            'delivery_city', 'expected_delivery', 'masked_receiver', 'events'
        ]

    def get_masked_receiver(self, obj):
        name = obj.receiver_name or ""
        if len(name) <= 2:
            return "**"
        return f"{name[0]}***{name[-1]}"
