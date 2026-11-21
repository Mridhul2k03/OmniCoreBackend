from rest_framework import serializers
from apps.core.phone_validation import PhoneNumberValidationMixin
from apps.courier.models import (
    Hub, CourierAgent, Shipment, ShipmentParcel, PickupLocation,
    ShipmentPickup, SortingRecord, TrackingEvent, Delivery,
    DeliveryAttempt, ProofOfDelivery, CourierCommission, CourierExpense, CourierPayout,
    HubConvoy
)
from apps.courier.services import generate_awb
from django.utils import timezone
from django.db import transaction
from apps.core.middleware import resolve_tenant_context


class HubSerializer(PhoneNumberValidationMixin, serializers.ModelSerializer):
    current_parcels_count = serializers.SerializerMethodField()
    incoming_shipments_count = serializers.SerializerMethodField()
    pending_sorting_count = serializers.SerializerMethodField()
    sorted_shipments_count = serializers.SerializerMethodField()
    outgoing_shipments_count = serializers.SerializerMethodField()

    class Meta:
        model = Hub
        fields = [
            'id', 'name', 'code', 'address', 'city', 'state',
            'postal_code', 'contact_phone', 'contact_email',
            'status', 'capacity_sqft', 'manager', 'created_at', 'updated_at',
            'current_parcels_count', 'incoming_shipments_count', 'pending_sorting_count',
            'sorted_shipments_count', 'outgoing_shipments_count'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_current_parcels_count(self, obj):
        # Sorted shipments remain physically staged at this hub until a convoy departs.
        return obj.hub_shipments.filter(status__in=['RECEIVED', 'STORED', 'SORTED']).count()

    def get_incoming_shipments_count(self, obj):
        return Shipment.objects.filter(tenant=obj.tenant, destination_hub=obj, status='IN_TRANSIT').count()

    def get_pending_sorting_count(self, obj):
        return SortingRecord.objects.filter(tenant=obj.tenant, source_hub=obj).exclude(status='SORTED').count()

    def get_sorted_shipments_count(self, obj):
        return SortingRecord.objects.filter(tenant=obj.tenant, source_hub=obj, status='SORTED').count()

    def get_outgoing_shipments_count(self, obj):
        return obj.hub_shipments.filter(status='DISPATCHED').count()


class CourierAgentSerializer(serializers.ModelSerializer):
    display_name = serializers.ReadOnlyField()
    driver_name = serializers.CharField(source='driver.full_name', read_only=True, default='')
    driver_phone = serializers.CharField(source='driver.phone', read_only=True, default='')
    driver_email = serializers.CharField(source='driver.email', read_only=True, default='')
    vehicle_registration = serializers.CharField(source='vehicle.registration_number', read_only=True, default='')
    vehicle_type = serializers.CharField(source='vehicle.category.name', read_only=True, default='')
    assigned_deliveries_count = serializers.SerializerMethodField()
    completed_deliveries_count = serializers.SerializerMethodField()
    commission_earned_total = serializers.SerializerMethodField()
    expenses_total = serializers.SerializerMethodField()
    pending_payout_amount = serializers.SerializerMethodField()
    paid_amount_total = serializers.SerializerMethodField()

    class Meta:
        model = CourierAgent
        fields = [
            'id', 'agent_code', 'driver', 'user', 'vehicle', 'service_area',
            'status', 'commission_rate_per_delivery', 'current_hub',
            'display_name', 'driver_name', 'driver_phone', 'driver_email', 'vehicle_registration', 'vehicle_type',
            'assigned_deliveries_count', 'completed_deliveries_count', 'commission_earned_total',
            'expenses_total', 'pending_payout_amount', 'paid_amount_total', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'display_name', 'driver_name', 'driver_phone', 'driver_email', 'vehicle_registration', 'vehicle_type', 'assigned_deliveries_count', 'completed_deliveries_count', 'commission_earned_total', 'expenses_total', 'pending_payout_amount', 'paid_amount_total', 'created_at', 'updated_at']

    def get_assigned_deliveries_count(self, obj):
        return obj.deliveries.filter(delivery_status__in=['PENDING', 'ASSIGNED', 'OUT_FOR_DELIVERY']).count()

    def get_completed_deliveries_count(self, obj):
        return obj.deliveries.filter(delivery_status='DELIVERED').count()

    def get_commission_earned_total(self, obj):
        from django.db.models import Sum
        return obj.commissions.filter(status='EARNED').aggregate(total=Sum('commission_amount'))['total'] or 0

    def get_expenses_total(self, obj):
        from django.db.models import Sum
        return obj.expenses.aggregate(total=Sum('amount'))['total'] or 0

    def get_pending_payout_amount(self, obj):
        from django.db.models import Sum
        return obj.payouts.exclude(status__in=['PAID', 'REJECTED']).aggregate(total=Sum('net_payable'))['total'] or 0

    def get_paid_amount_total(self, obj):
        from django.db.models import Sum
        return obj.payouts.filter(status='PAID').aggregate(total=Sum('net_payable'))['total'] or 0


class ShipmentParcelSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShipmentParcel
        fields = ['id', 'barcode', 'weight_kg', 'dimensions', 'description']
        read_only_fields = ['id']


class PickupLocationSerializer(PhoneNumberValidationMixin, serializers.ModelSerializer):
    class Meta:
        model = PickupLocation
        fields = ['id', 'name', 'contact_person', 'contact_phone', 'address', 'city', 'postal_code', 'notes']
        read_only_fields = ['id']


class ShipmentPickupSerializer(PhoneNumberValidationMixin, serializers.ModelSerializer):
    shipment_awb = serializers.CharField(source='shipment.awb_number', read_only=True)
    agent_name = serializers.CharField(source='assigned_agent.display_name', read_only=True, default='')
    destination_hub_name = serializers.CharField(source='shipment.destination_hub.name', read_only=True, default='')

    class Meta:
        model = ShipmentPickup
        fields = [
            'id', 'shipment', 'shipment_awb', 'destination_hub_name', 'pickup_location', 'location_name', 'sequence', 'parcel_count', 'address',
            'contact_name', 'contact_phone', 'scheduled_time', 'assigned_agent',
            'agent_name', 'status', 'actual_pickup_time', 'failure_reason', 'notes', 'created_at'
        ]
        read_only_fields = ['id', 'shipment_awb', 'destination_hub_name', 'agent_name', 'created_at']


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


class DeliverySerializer(PhoneNumberValidationMixin, serializers.ModelSerializer):
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


class ShipmentSerializer(PhoneNumberValidationMixin, serializers.ModelSerializer):
    parcels = ShipmentParcelSerializer(many=True, required=False)
    pickups = ShipmentPickupSerializer(many=True, required=False)
    tracking_events = TrackingEventSerializer(many=True, read_only=True)
    delivery_task = DeliverySerializer(read_only=True)
    assigned_agent_name = serializers.CharField(source='assigned_agent.display_name', read_only=True, default='')

    class Meta:
        model = Shipment
        fields = [
            'id', 'awb_number', 'customer', 'invoice', 'sender_name', 'sender_phone',
            'sender_email', 'sender_address', 'sender_city', 'sender_postal_code',
            'receiver_name', 'receiver_phone', 'receiver_email', 'delivery_address',
            'delivery_city', 'delivery_postal_code', 'service_type', 'weight_kg',
            'dimensions', 'parcel_count', 'declared_value', 'shipping_cost',
            'origin_hub', 'current_hub', 'destination_hub', 'assigned_agent', 'assigned_agent_name',
            'status', 'expected_delivery', 'notes', 'parcels', 'pickups',
            'tracking_events', 'delivery_task', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'awb_number', 'status', 'created_at', 'updated_at']

    @transaction.atomic
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
        Delivery.objects.create(
            tenant=shipment.tenant,
            shipment=shipment,
            scheduled_delivery=shipment.expected_delivery.date() if shipment.expected_delivery else timezone.localdate(),
            delivery_address=shipment.delivery_address,
            recipient_name=shipment.receiver_name,
            recipient_phone=shipment.receiver_phone,
        )
        return shipment


class CourierCommissionSerializer(serializers.ModelSerializer):
    agent_name = serializers.ReadOnlyField(source='agent.display_name')
    shipment_awb = serializers.ReadOnlyField(source='shipment.awb_number')

    class Meta:
        model = CourierCommission
        fields = ['id', 'agent', 'agent_name', 'delivery', 'shipment', 'shipment_awb', 'commission_amount', 'date', 'status']
        read_only_fields = ['id', 'agent_name', 'shipment_awb', 'date']


class CourierExpenseSerializer(serializers.ModelSerializer):
    agent_name = serializers.ReadOnlyField(source='agent.display_name')

    class Meta:
        model = CourierExpense
        fields = ['id', 'agent', 'agent_name', 'expense_type', 'amount', 'date', 'notes', 'is_approved']
        read_only_fields = ['id', 'agent_name', 'date']


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


class HubConvoySerializer(serializers.ModelSerializer):
    origin_hub_name = serializers.CharField(source='origin_hub.name', read_only=True)
    destination_hub_name = serializers.CharField(source='destination_hub.name', read_only=True)
    vehicle_registration = serializers.CharField(source='vehicle.registration_number', read_only=True, default='')
    driver_name = serializers.CharField(source='driver.full_name', read_only=True, default='')
    shipments = serializers.PrimaryKeyRelatedField(many=True, queryset=Shipment.objects.all())
    shipment_awbs = serializers.SerializerMethodField()

    class Meta:
        model = HubConvoy
        fields = [
            'id', 'convoy_number', 'origin_hub', 'origin_hub_name', 'destination_hub',
            'destination_hub_name', 'vehicle', 'vehicle_registration', 'driver', 'driver_name',
            'shipments', 'shipment_awbs', 'status', 'scheduled_departure', 'departed_at',
            'arrived_at', 'notes', 'created_at',
        ]
        read_only_fields = ['id', 'convoy_number', 'origin_hub_name', 'destination_hub_name',
                            'vehicle_registration', 'driver_name', 'shipment_awbs', 'status',
                            'departed_at', 'arrived_at', 'created_at']

    def validate(self, attrs):
        tenant, _ = resolve_tenant_context(self.context['request'])
        related = [attrs.get('origin_hub'), attrs.get('destination_hub')]
        related += list(attrs.get('shipments', []))
        related += [attrs.get('vehicle'), attrs.get('driver')]
        if any(value is not None and value.tenant_id != tenant.id for value in related):
            raise serializers.ValidationError('All convoy resources must belong to the active tenant.')
        if attrs.get('origin_hub') == attrs.get('destination_hub'):
            raise serializers.ValidationError({'destination_hub': 'Choose a different destination hub.'})
        if not attrs.get('shipments'):
            raise serializers.ValidationError({'shipments': 'Select at least one shipment.'})
        return attrs

    def create(self, validated_data):
        shipments = validated_data.pop('shipments')
        validated_data['convoy_number'] = f"CV-{timezone.now():%Y%m%d}-{uuid.uuid4().hex[:6].upper()}"
        convoy = HubConvoy.objects.create(**validated_data)
        convoy.shipments.set(shipments)
        return convoy

    def get_shipment_awbs(self, obj):
        return list(obj.shipments.values_list('awb_number', flat=True))


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
