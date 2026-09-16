from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from apps.core.viewsets import TenantModelViewSet

from apps.courier.models import (
    Hub, CourierAgent, Shipment, ShipmentPickup, SortingRecord,
    TrackingEvent, Delivery, ProofOfDelivery, CourierCommission,
    CourierExpense, CourierPayout
)
from apps.courier.serializers import (
    HubSerializer, CourierAgentSerializer, ShipmentSerializer,
    ShipmentPickupSerializer, SortingRecordSerializer,
    TrackingEventSerializer, DeliverySerializer, ProofOfDeliverySerializer,
    CourierCommissionSerializer, CourierExpenseSerializer, CourierPayoutSerializer
)
from apps.courier.services import (
    ShipmentWorkflowService, HubSortingService, ProofOfDeliveryService,
    CourierPayoutService
)


class HubViewSet(TenantModelViewSet):
    queryset = Hub.objects.all()
    serializer_class = HubSerializer
    search_fields = ['name', 'code', 'city', 'postal_code']
    filterset_fields = ['status', 'city']


class CourierAgentViewSet(TenantModelViewSet):
    queryset = CourierAgent.objects.select_related('driver', 'user', 'vehicle', 'current_hub').all()
    serializer_class = CourierAgentSerializer
    search_fields = ['agent_code', 'driver__first_name', 'driver__last_name', 'user__first_name', 'user__last_name']
    filterset_fields = ['status', 'current_hub']


class ShipmentViewSet(TenantModelViewSet):
    queryset = Shipment.objects.select_related('origin_hub', 'current_hub', 'destination_hub', 'assigned_agent').prefetch_related('parcels', 'pickups', 'tracking_events').all()
    serializer_class = ShipmentSerializer
    search_fields = ['awb_number', 'sender_name', 'receiver_name', 'receiver_phone', 'delivery_postal_code']
    filterset_fields = ['status', 'service_type', 'current_hub', 'destination_hub']

    @action(detail=True, methods=['post'], url_path='transition')
    def transition(self, request, pk=None):
        shipment = self.get_object()
        new_status = request.data.get('status')
        location = request.data.get('location', '')
        description = request.data.get('description', '')
        metadata = request.data.get('metadata', {})
        
        event = ShipmentWorkflowService.transition_status(
            shipment=shipment,
            new_status=new_status,
            actor=request.user,
            location=location,
            description=description,
            metadata=metadata
        )
        return Response({
            'status': shipment.status,
            'event': TrackingEventSerializer(event).data
        })

    @action(detail=True, methods=['get'], url_path='tracking')
    def tracking(self, request, pk=None):
        shipment = self.get_object()
        events = shipment.tracking_events.all().order_by('timestamp')
        return Response(TrackingEventSerializer(events, many=True).data)


class ShipmentPickupViewSet(TenantModelViewSet):
    queryset = ShipmentPickup.objects.select_related('shipment', 'assigned_agent').all()
    serializer_class = ShipmentPickupSerializer
    filterset_fields = ['status', 'assigned_agent']

    @action(detail=True, methods=['post'], url_path='assign')
    def assign(self, request, pk=None):
        pickup = self.get_object()
        agent_id = request.data.get('agent_id')
        notes = request.data.get('notes', '')
        if agent_id:
            pickup.assigned_agent_id = agent_id
        pickup = ShipmentWorkflowService.record_pickup_progress(pickup, "ASSIGN", actor=request.user, notes=notes)
        return Response(ShipmentPickupSerializer(pickup).data)

    @action(detail=True, methods=['post'], url_path='start')
    def start_pickup(self, request, pk=None):
        pickup = self.get_object()
        notes = request.data.get('notes', '')
        pickup = ShipmentWorkflowService.record_pickup_progress(pickup, "START", actor=request.user, notes=notes)
        return Response(ShipmentPickupSerializer(pickup).data)

    @action(detail=True, methods=['post'], url_path='complete')
    def complete_pickup(self, request, pk=None):
        pickup = self.get_object()
        notes = request.data.get('notes', '')
        pickup = ShipmentWorkflowService.record_pickup_progress(pickup, "COMPLETE", actor=request.user, notes=notes)
        return Response(ShipmentPickupSerializer(pickup).data)

    @action(detail=True, methods=['post'], url_path='fail')
    def fail_pickup(self, request, pk=None):
        pickup = self.get_object()
        reason = request.data.get('reason', 'Consignee unavailable')
        notes = request.data.get('notes', '')
        pickup = ShipmentWorkflowService.record_pickup_progress(pickup, "FAIL", actor=request.user, reason=reason, notes=notes)
        return Response(ShipmentPickupSerializer(pickup).data)


class SortingRecordViewSet(TenantModelViewSet):
    queryset = SortingRecord.objects.select_related('shipment', 'source_hub', 'destination_hub', 'operator').all()
    serializer_class = SortingRecordSerializer
    filterset_fields = ['source_hub', 'destination_hub', 'status']

    @action(detail=False, methods=['post'], url_path='process')
    def process_sorting(self, request):
        shipment_id = request.data.get('shipment_id')
        source_hub_id = request.data.get('source_hub_id')
        destination_hub_id = request.data.get('destination_hub_id')
        sorting_category = request.data.get('sorting_category', 'STANDARD')
        notes = request.data.get('notes', '')

        shipment = Shipment.objects.filter(tenant=self.tenant, id=shipment_id).first()
        if not shipment:
            return Response({'error': 'Shipment not found'}, status=status.HTTP_404_NOT_FOUND)
            
        source_hub = Hub.objects.filter(tenant=self.tenant, id=source_hub_id).first()
        if not source_hub:
            return Response({'error': 'Source Hub not found'}, status=status.HTTP_404_NOT_FOUND)

        dest_hub = None
        if destination_hub_id:
            dest_hub = Hub.objects.filter(tenant=self.tenant, id=destination_hub_id).first()

        record = HubSortingService.process_sorting(
            shipment=shipment,
            source_hub=source_hub,
            destination_hub=dest_hub,
            operator=request.user,
            sorting_category=sorting_category,
            notes=notes
        )
        return Response(SortingRecordSerializer(record).data, status=status.HTTP_201_CREATED)


class DeliveryViewSet(TenantModelViewSet):
    queryset = Delivery.objects.select_related('shipment', 'agent').all()
    serializer_class = DeliverySerializer
    filterset_fields = ['delivery_status', 'agent', 'scheduled_delivery']

    @action(detail=True, methods=['post'], url_path='generate-otp')
    def generate_otp(self, request, pk=None):
        delivery = self.get_object()
        otp = ProofOfDeliveryService.generate_otp_for_delivery(delivery)
        return Response({'message': 'OTP generated successfully', 'otp': otp})

    @action(detail=True, methods=['post'], url_path='verify-pod')
    def verify_pod(self, request, pk=None):
        delivery = self.get_object()
        entered_otp = request.data.get('otp')
        recipient_name = request.data.get('recipient_name', delivery.recipient_name)
        signature_file = request.data.get('signature_file', '')
        notes = request.data.get('notes', '')

        pod = ProofOfDeliveryService.verify_and_complete_pod(
            delivery=delivery,
            entered_otp=entered_otp,
            signature_file=signature_file,
            recipient_name=recipient_name,
            agent=delivery.agent,
            notes=notes
        )
        return Response(ProofOfDeliverySerializer(pod).data)


class ProofOfDeliveryViewSet(TenantModelViewSet):
    queryset = ProofOfDelivery.objects.select_related('delivery', 'agent').all()
    serializer_class = ProofOfDeliverySerializer


class CourierCommissionViewSet(TenantModelViewSet):
    queryset = CourierCommission.objects.select_related('agent', 'shipment', 'delivery').all()
    serializer_class = CourierCommissionSerializer
    filterset_fields = ['agent', 'status']


class CourierExpenseViewSet(TenantModelViewSet):
    queryset = CourierExpense.objects.select_related('agent').all()
    serializer_class = CourierExpenseSerializer
    filterset_fields = ['agent', 'is_approved']


class CourierPayoutViewSet(TenantModelViewSet):
    queryset = CourierPayout.objects.select_related('agent').all()
    serializer_class = CourierPayoutSerializer
    filterset_fields = ['agent', 'status']

    @action(detail=False, methods=['post'], url_path='process')
    def process_payout(self, request):
        agent_id = request.data.get('agent_id')
        period_start = request.data.get('period_start')
        period_end = request.data.get('period_end')
        idempotency_key = request.data.get('idempotency_key')

        agent = CourierAgent.objects.filter(tenant=self.tenant, id=agent_id).first()
        if not agent:
            return Response({'error': 'Courier Agent not found'}, status=status.HTTP_404_NOT_FOUND)

        payout = CourierPayoutService.process_agent_payout(
            agent=agent,
            period_start=period_start,
            period_end=period_end,
            idempotency_key=idempotency_key,
            actor=request.user
        )
        return Response(CourierPayoutSerializer(payout).data, status=status.HTTP_201_CREATED)
