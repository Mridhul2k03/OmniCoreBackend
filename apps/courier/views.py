from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import transaction
from django.utils import timezone
from apps.core.viewsets import TenantModelViewSet
from apps.core.middleware import resolve_tenant_context

from apps.courier.models import (
    Hub, CourierAgent, Shipment, ShipmentPickup, SortingRecord,
    TrackingEvent, Delivery, DeliveryAttempt, ProofOfDelivery, CourierCommission,
    CourierExpense, CourierPayout, VerificationMethod, PayoutStatus, HubConvoy,
    ShipmentStatus
)
from apps.courier.serializers import (
    HubSerializer, CourierAgentSerializer, ShipmentSerializer,
    ShipmentPickupSerializer, SortingRecordSerializer,
    TrackingEventSerializer, DeliverySerializer, ProofOfDeliverySerializer,
    CourierCommissionSerializer, CourierExpenseSerializer, CourierPayoutSerializer,
    HubConvoySerializer
)
from apps.courier.services import (
    ShipmentWorkflowService, HubSortingService, ProofOfDeliveryService,
    CourierPayoutService, HubConvoyService
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

    @action(detail=True, methods=['post'], url_path='attempts')
    def record_attempt(self, request, pk=None):
        shipment = self.get_object()
        delivery = Delivery.objects.filter(tenant=shipment.tenant, shipment=shipment).first()
        if not delivery:
            return Response({'detail': 'Delivery task not found for this shipment.'}, status=status.HTTP_404_NOT_FOUND)
        reason = str(request.data.get('reason', '')).strip()
        if not reason:
            return Response({'reason': ['This field is required.']}, status=status.HTTP_400_BAD_REQUEST)
        attempt_number = delivery.attempt_count + 1
        attempt = DeliveryAttempt.objects.create(
            tenant=shipment.tenant,
            delivery=delivery,
            attempt_number=attempt_number,
            reason=reason[:100],
            notes=str(request.data.get('agent_name', ''))[:500],
        )
        delivery.attempt_count = attempt_number
        delivery.delivery_status = 'ATTEMPTED'
        delivery.save(update_fields=['attempt_count', 'delivery_status', 'updated_at'])
        shipment.status = 'DELIVERY_ATTEMPTED'
        shipment.save(update_fields=['status', 'updated_at'])
        TrackingEvent.objects.create(
            tenant=shipment.tenant,
            shipment=shipment,
            event_type='DELIVERY_ATTEMPTED',
            status=shipment.status,
            location=shipment.delivery_city,
            actor=request.user,
            description=f'Delivery attempt {attempt_number}: {reason}',
        )
        return Response(ShipmentSerializer(shipment).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='assign-agent')
    def assign_agent(self, request, pk=None):
        shipment = self.get_object()
        tenant, _ = resolve_tenant_context(request)
        agent = CourierAgent.objects.filter(tenant=tenant, id=request.data.get('agent_id'), status='ACTIVE').first()
        if not agent:
            return Response({'agent_id': ['Select an active courier agent in this workspace.']}, status=status.HTTP_400_BAD_REQUEST)
        if shipment.status not in [ShipmentStatus.SORTED, ShipmentStatus.DESTINATION_HUB, ShipmentStatus.OUT_FOR_DELIVERY, ShipmentStatus.DELIVERY_ATTEMPTED]:
            return Response({'detail': 'Sort the shipment at a hub before assigning last-mile delivery.'}, status=status.HTTP_400_BAD_REQUEST)
        shipment.assigned_agent = agent
        shipment.status = ShipmentStatus.OUT_FOR_DELIVERY
        shipment.save(update_fields=['assigned_agent', 'status', 'updated_at'])
        delivery, _ = Delivery.objects.get_or_create(
            tenant=tenant, shipment=shipment,
            defaults={
                'scheduled_delivery': shipment.expected_delivery.date() if shipment.expected_delivery else timezone.localdate(),
                'delivery_address': shipment.delivery_address,
                'recipient_name': shipment.receiver_name,
                'recipient_phone': shipment.receiver_phone,
            },
        )
        delivery.agent = agent
        delivery.delivery_status = 'OUT_FOR_DELIVERY'
        delivery.save(update_fields=['agent', 'delivery_status', 'updated_at'])
        TrackingEvent.objects.create(
            tenant=tenant, shipment=shipment, event_type='OUT_FOR_DELIVERY', status=shipment.status,
            location=shipment.delivery_city, actor=request.user,
            description=f'Assigned to courier agent {agent.display_name}.',
        )
        return Response(ShipmentSerializer(shipment).data)


class ShipmentPickupViewSet(TenantModelViewSet):
    queryset = ShipmentPickup.objects.select_related('shipment', 'assigned_agent').all()
    serializer_class = ShipmentPickupSerializer
    filterset_fields = ['status', 'assigned_agent']

    @action(detail=False, methods=['post'], url_path='batch')
    def create_batch(self, request):
        tenant, _ = resolve_tenant_context(request)
        shipment = Shipment.objects.filter(tenant=tenant, id=request.data.get('shipment_id')).first()
        if not shipment:
            return Response({'shipment_id': ['Select a shipment in this workspace.']}, status=status.HTTP_400_BAD_REQUEST)
        agent_id = request.data.get('assigned_agent_id')
        agent = None
        if agent_id:
            agent = CourierAgent.objects.filter(tenant=tenant, id=agent_id, status='ACTIVE').first()
            if not agent:
                return Response({'assigned_agent_id': ['Select an active courier agent.']}, status=status.HTTP_400_BAD_REQUEST)
        stops = request.data.get('stops')
        if not isinstance(stops, list) or not stops or len(stops) > 30:
            return Response({'stops': ['Provide between 1 and 30 pickup stops.']}, status=status.HTTP_400_BAD_REQUEST)

        serializers = []
        for sequence, stop in enumerate(stops, start=1):
            stop_data = {
                'shipment': str(shipment.id), 'sequence': sequence,
                'location_name': stop.get('location_name', ''), 'address': stop.get('address', ''),
                'contact_name': stop.get('contact_name', ''), 'contact_phone': stop.get('contact_phone', ''),
                'scheduled_time': stop.get('scheduled_time'), 'parcel_count': stop.get('parcel_count', 1),
                'assigned_agent': str(agent.id) if agent else None,
                'status': 'ASSIGNED' if agent else 'PENDING', 'notes': stop.get('notes', ''),
            }
            serializer = ShipmentPickupSerializer(data=stop_data)
            serializer.is_valid(raise_exception=True)
            serializers.append(serializer)
        with transaction.atomic():
            created = [serializer.save(tenant=tenant) for serializer in serializers]
            if agent and shipment.status == ShipmentStatus.BOOKED:
                ShipmentWorkflowService.transition_status(
                    shipment, ShipmentStatus.PICKUP_ASSIGNED, actor=request.user,
                    description=f'Pickup batch with {len(created)} sequenced stops assigned to {agent.display_name}.',
                )
        return Response(ShipmentPickupSerializer(created, many=True).data, status=status.HTTP_201_CREATED)

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
        tenant, _ = resolve_tenant_context(request)
        shipment_id = request.data.get('shipment_id')
        source_hub_id = request.data.get('source_hub_id')
        destination_hub_id = request.data.get('destination_hub_id')
        sorting_category = request.data.get('sorting_category', 'STANDARD')
        notes = request.data.get('notes', '')

        shipment = Shipment.objects.filter(tenant=tenant, id=shipment_id).first()
        if not shipment:
            return Response({'error': 'Shipment not found'}, status=status.HTTP_404_NOT_FOUND)
            
        source_hub = Hub.objects.filter(tenant=tenant, id=source_hub_id).first()
        if not source_hub:
            return Response({'error': 'Source Hub not found'}, status=status.HTTP_404_NOT_FOUND)

        dest_hub = None
        if destination_hub_id:
            dest_hub = Hub.objects.filter(tenant=tenant, id=destination_hub_id).first()

        record = HubSortingService.process_sorting(
            shipment=shipment,
            source_hub=source_hub,
            destination_hub=dest_hub,
            operator=request.user,
            sorting_category=sorting_category,
            notes=notes
        )
        return Response(SortingRecordSerializer(record).data, status=status.HTTP_201_CREATED)


class HubConvoyViewSet(TenantModelViewSet):
    queryset = HubConvoy.objects.select_related('origin_hub', 'destination_hub', 'vehicle', 'driver').prefetch_related('shipments').all()
    serializer_class = HubConvoySerializer
    filterset_fields = ['status', 'origin_hub', 'destination_hub']
    required_permission = 'courier.dispatch'

    @action(detail=True, methods=['post'], url_path='dispatch')
    def dispatch(self, request, pk=None):
        convoy = HubConvoyService.dispatch(self.get_object(), actor=request.user)
        return Response(HubConvoySerializer(convoy).data)

    @action(detail=True, methods=['post'], url_path='arrive')
    def arrive(self, request, pk=None):
        convoy = HubConvoyService.arrive(self.get_object(), actor=request.user)
        return Response(HubConvoySerializer(convoy).data)


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
        verification_method = str(request.data.get('verification_method', VerificationMethod.OTP)).upper()
        if verification_method not in VerificationMethod.values:
            return Response({'verification_method': ['Select a valid verification method.']}, status=status.HTTP_400_BAD_REQUEST)
        pod, _ = ProofOfDelivery.objects.get_or_create(
            tenant=delivery.tenant,
            delivery=delivery,
            defaults={'recipient_name': delivery.recipient_name, 'verification_method': verification_method},
        )
        if pod.verification_method != verification_method:
            pod.verification_method = verification_method
            pod.save(update_fields=['verification_method'])
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

    @action(detail=True, methods=['post'], url_path='approve')
    def approve(self, request, pk=None):
        payout = self.get_object()
        if payout.status not in [PayoutStatus.PENDING, PayoutStatus.PROCESSING]:
            return Response({'detail': 'Only pending payouts can be approved.'}, status=status.HTTP_400_BAD_REQUEST)
        payout.status = PayoutStatus.APPROVED
        payout.save(update_fields=['status', 'updated_at'])
        return Response(CourierPayoutSerializer(payout).data)

    @action(detail=True, methods=['post'], url_path='pay')
    def pay(self, request, pk=None):
        payout = CourierPayoutService.pay_payout(self.get_object(), actor=request.user)
        return Response(CourierPayoutSerializer(payout).data)

    @action(detail=False, methods=['post'], url_path='process')
    def process_payout(self, request):
        tenant, _ = resolve_tenant_context(request)
        agent_id = request.data.get('agent_id')
        period_start = request.data.get('period_start')
        period_end = request.data.get('period_end')
        idempotency_key = request.data.get('idempotency_key')

        agent = CourierAgent.objects.filter(tenant=tenant, id=agent_id).first()
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
