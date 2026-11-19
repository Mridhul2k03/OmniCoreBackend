import uuid
from django.db import transaction
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework.throttling import AnonRateThrottle
from apps.core.viewsets import TenantModelViewSet
from apps.tenants.models import Tenant, TenantStatus
from apps.website.models import (
    TenantWebsite, WebsitePage, WebsiteSection, WebsiteService,
    WebsiteBlogPost, WebsiteFAQ, WebsiteBookingConfiguration
)
from apps.website.serializers import (
    TenantWebsiteSerializer, WebsitePageSerializer, WebsiteSectionSerializer,
    WebsiteServiceSerializer, WebsiteBlogPostSerializer, WebsiteFAQSerializer,
    WebsiteBookingConfigurationSerializer,
    PublicCourierBookingSerializer, PublicTaxiBookingSerializer,
    PublicBusBookingSerializer, PublicTransportRequestSerializer, PublicBookingSerializer
)
from apps.courier.models import Shipment, ShipmentStatus
from apps.courier.serializers import PublicTrackingSerializer
from apps.courier.services import generate_awb
from apps.crm.models import Customer, CustomerType
from apps.trips.models import Booking, BookingStatus


class TenantWebsiteViewSet(TenantModelViewSet):
    queryset = TenantWebsite.objects.prefetch_related('pages', 'services').all()
    serializer_class = TenantWebsiteSerializer


class WebsitePageViewSet(TenantModelViewSet):
    queryset = WebsitePage.objects.prefetch_related('sections').all()
    serializer_class = WebsitePageSerializer
    filterset_fields = ['is_published']


class WebsiteSectionViewSet(TenantModelViewSet):
    queryset = WebsiteSection.objects.all()
    serializer_class = WebsiteSectionSerializer
    filterset_fields = ['page', 'section_type']


class WebsiteServiceViewSet(TenantModelViewSet):
    queryset = WebsiteService.objects.all()
    serializer_class = WebsiteServiceSerializer
    filterset_fields = ['vertical', 'is_featured']


class WebsiteBlogPostViewSet(TenantModelViewSet):
    queryset = WebsiteBlogPost.objects.all()
    serializer_class = WebsiteBlogPostSerializer
    filterset_fields = ['is_published']


class WebsiteFAQViewSet(TenantModelViewSet):
    queryset = WebsiteFAQ.objects.all()
    serializer_class = WebsiteFAQSerializer
    filterset_fields = ['category']


class WebsiteBookingConfigurationViewSet(TenantModelViewSet):
    queryset = WebsiteBookingConfiguration.objects.all()
    serializer_class = WebsiteBookingConfigurationSerializer


# ============================================================
# PUBLIC ENGINE VIEWS (Unauthenticated, Rate-limited, Sanitized)
# ============================================================

def resolve_public_tenant(tenant_slug):
    """
    Safely resolves tenant and website configuration via subdomain or tenant slug.
    """
    website = TenantWebsite.objects.filter(subdomain=tenant_slug).select_related('tenant').first()
    if website and website.tenant and website.tenant.status == TenantStatus.ACTIVE:
        return website.tenant, website
    tenant = Tenant.objects.filter(slug=tenant_slug, status=TenantStatus.ACTIVE).first()
    if tenant:
        website = TenantWebsite.objects.filter(tenant=tenant).first()
        return tenant, website
    return None, None


def get_public_booking_config_error(website, service_type):
    aliases = {
        'courier_express': {'courier', 'courier_express', 'express', 'express_parcel'},
        'corporate_shuttle': {'shuttle', 'corporate_shuttle', 'passenger_transport', 'taxi', 'bus'},
        'freight_logistics': {'freight', 'freight_logistics', 'transport'},
        'cold_chain': {'cold_chain', 'coldchain', 'reefer'},
        'taxi': {'taxi', 'shuttle', 'corporate_shuttle'},
        'bus': {'bus', 'shuttle', 'corporate_shuttle'},
        'freight': {'freight', 'freight_logistics', 'transport'},
    }
    enabled = {
        str(value).strip().lower().replace('-', '_').replace(' ', '_')
        for value in (website.enabled_verticals or [])
    }
    if enabled and not (enabled & aliases.get(service_type, {service_type})):
        return 'This service is not enabled for this tenant.'
    booking_config = WebsiteBookingConfiguration.objects.filter(website=website).first()
    if booking_config and booking_config.require_phone_verification:
        return 'Phone verification is required, but this portal has no phone verification flow configured.'
    return None


class PublicWebsiteConfigView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [AnonRateThrottle]

    def get(self, request, tenant_slug):
        tenant, website = resolve_public_tenant(tenant_slug)
        if not tenant:
            return Response({'error': 'Tenant website not found.'}, status=status.HTTP_404_NOT_FOUND)

        if not website or not website.is_published:
            return Response({
                'company_name': tenant.company_name,
                'slug': tenant.slug,
                'is_published': False,
                'message': 'Website not published.'
            }, status=status.HTTP_200_OK)

        serializer = TenantWebsiteSerializer(website)
        public_data = serializer.data
        public_data['pages'] = [page for page in public_data.get('pages', []) if page.get('is_published')]
        public_data['services'] = [service for service in public_data.get('services', []) if service.get('is_featured')]
        return Response(public_data, status=status.HTTP_200_OK)


class PublicBookingView(APIView):
    """Create a courier shipment or an operations booking from the public portal."""
    permission_classes = [AllowAny]
    throttle_classes = [AnonRateThrottle]

    def post(self, request, tenant_slug):
        tenant, website = resolve_public_tenant(tenant_slug)
        if not tenant or not website or not website.is_published:
            return Response({'error': 'Published tenant booking portal not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = PublicBookingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        service_type = data['service_type']

        config_error = get_public_booking_config_error(website, service_type)
        if config_error:
            return Response(
                {'error': config_error},
                status=status.HTTP_400_BAD_REQUEST,
            )
        booking_config = WebsiteBookingConfiguration.objects.filter(website=website).first()
        allow_instant_booking = booking_config.allow_instant_booking if booking_config else True

        extra_notes = []
        if data.get('cargo_description'):
            extra_notes.append(f"Cargo: {data['cargo_description']}")
        if data.get('temperature_range') and service_type == 'cold_chain':
            extra_notes.append(f"Temperature requirement: {data['temperature_range']}")
        if service_type == 'corporate_shuttle':
            extra_notes.append(f"Passenger count: {data['passenger_count']}")
        if data.get('coupon_code'):
            extra_notes.append(f"Promotion code provided: {data['coupon_code']}")
        if data.get('notes'):
            extra_notes.append(data['notes'])
        notes = '\n'.join(extra_notes)

        with transaction.atomic():
            if service_type == 'courier_express':
                customer = Customer.objects.filter(
                    tenant=tenant, phone=data['sender_phone'], is_active=True
                ).first()
                shipment = Shipment.objects.create(
                    tenant=tenant,
                    customer=customer,
                    awb_number=generate_awb(),
                    sender_name=data['sender_name'],
                    sender_phone=data['sender_phone'],
                    sender_email=data.get('sender_email', ''),
                    sender_address=data['sender_address'],
                    sender_city=data['sender_city'],
                    sender_postal_code=data['sender_postal_code'],
                    receiver_name=data['receiver_name'],
                    receiver_phone=data['receiver_phone'],
                    delivery_address=data['delivery_address'],
                    delivery_city=data['delivery_city'],
                    delivery_postal_code=data['delivery_postal_code'],
                    service_type='EXPRESS',
                    weight_kg=data['estimated_weight_kg'],
                    notes=notes,
                    status=ShipmentStatus.BOOKED,
                )

                from apps.courier.models import TrackingEvent
                TrackingEvent.objects.create(
                    tenant=tenant,
                    shipment=shipment,
                    event_type='PUBLIC_BOOKING',
                    status=ShipmentStatus.BOOKED,
                    location=shipment.sender_city,
                    description='Shipment request received through the public booking portal.',
                )
                reference = shipment.awb_number
                message = 'Your shipment request has been received. Use the AWB to track its operational status.'
                return Response({
                    'success': True,
                    'booking_reference': reference,
                    'booking_type': 'shipment',
                    'awb_number': shipment.awb_number,
                    'tracking_url': f"/api/v1/public/tracking/{shipment.awb_number}/",
                    'status': shipment.status,
                    'message': message,
                }, status=status.HTTP_201_CREATED)

            vertical = service_type
            vehicle_types = {
                'corporate_shuttle': 'passenger_van',
                'freight_logistics': 'heavy_truck',
                'cold_chain': 'reefer_truck',
            }
            scheduled_date = data.get('pickup_time')
            booking = create_public_trip_booking(
                tenant,
                customer_name=data['sender_name'],
                phone=data['sender_phone'],
                email=data.get('sender_email', ''),
                address=data['sender_address'],
                pickup=f"{data['sender_address']}, {data['sender_city']} {data['sender_postal_code']}",
                dropoff=f"{data['delivery_address']}, {data['delivery_city']} {data['delivery_postal_code']}",
                cargo_type=data.get('cargo_description') or service_type.replace('_', ' ').title(),
                vertical=vertical,
                vehicle_type=vehicle_types[service_type],
                weight_kg=data['estimated_weight_kg'],
                scheduled_date=scheduled_date.date() if scheduled_date else timezone.localdate(),
                notes=notes,
                status_value=BookingStatus.CONFIRMED if allow_instant_booking else BookingStatus.DRAFT,
            )

        return Response({
            'success': True,
            'booking_reference': booking.booking_number,
            'booking_type': 'trip_booking',
            'status': booking.status,
            'message': 'Your service request has been recorded.' if booking.status == BookingStatus.DRAFT else 'Your service booking has been confirmed.',
        }, status=status.HTTP_201_CREATED)


def create_public_trip_booking(tenant, *, customer_name, phone, email='', address='', pickup,
                               dropoff, vertical, vehicle_type, cargo_type, scheduled_date=None,
                               weight_kg=0, notes='', status_value=BookingStatus.DRAFT):
    """Persist a public service request in the same bookings queue used by operations."""
    with transaction.atomic():
        customer = Customer.objects.filter(tenant=tenant, phone=phone, is_active=True).first()
        if not customer:
            customer = Customer.objects.create(
                tenant=tenant,
                company_name=customer_name,
                contact_person=customer_name,
                phone=phone,
                email=email,
                address=address,
                customer_type=CustomerType.INDIVIDUAL,
            )
        return Booking.objects.create(
            tenant=tenant,
            booking_number=f"PB-{timezone.localdate():%Y%m%d}-{uuid.uuid4().hex[:10].upper()}",
            customer=customer,
            pickup_location=pickup,
            dropoff_location=dropoff,
            cargo_type=cargo_type,
            vertical=vertical,
            vehicle_type=vehicle_type,
            cargo_weight_kg=weight_kg,
            scheduled_date=scheduled_date or timezone.localdate(),
            status=status_value,
            notes=notes,
        )


class PublicCourierBookingView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [AnonRateThrottle]

    def post(self, request, tenant_slug):
        tenant, website = resolve_public_tenant(tenant_slug)
        if not tenant or not website or not website.is_published:
            return Response({'error': 'Tenant not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = PublicCourierBookingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        config_error = get_public_booking_config_error(website, 'courier_express')
        if config_error:
            return Response({'error': config_error}, status=status.HTTP_400_BAD_REQUEST)

        awb = generate_awb()
        shipment = Shipment.objects.create(
            tenant=tenant,
            awb_number=awb,
            sender_name=data['sender_name'],
            sender_phone=data['sender_phone'],
            sender_address=data['sender_address'],
            sender_city=data['sender_city'],
            sender_postal_code=data['sender_postal_code'],
            receiver_name=data['receiver_name'],
            receiver_phone=data['receiver_phone'],
            delivery_address=data['delivery_address'],
            delivery_city=data['delivery_city'],
            delivery_postal_code=data['delivery_postal_code'],
            service_type=data.get('service_type', 'STANDARD'),
            weight_kg=data.get('weight_kg', 1.0),
            declared_value=data.get('declared_value', 0.0),
            notes=data.get('notes', ''),
            status=ShipmentStatus.BOOKED
        )

        from apps.courier.models import TrackingEvent
        TrackingEvent.objects.create(
            tenant=tenant,
            shipment=shipment,
            event_type="PUBLIC_BOOKING",
            status=ShipmentStatus.BOOKED,
            location=shipment.sender_city,
            description="Shipment booked via public portal."
        )

        return Response({
            'success': True,
            'message': 'Shipment booked successfully.',
            'awb_number': shipment.awb_number,
            'tracking_url': f"/api/v1/public/tracking/{shipment.awb_number}/",
            'status': shipment.status
        }, status=status.HTTP_201_CREATED)


class PublicTaxiBookingView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [AnonRateThrottle]

    def post(self, request, tenant_slug):
        tenant, website = resolve_public_tenant(tenant_slug)
        if not tenant or not website or not website.is_published:
            return Response({'error': 'Tenant not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = PublicTaxiBookingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        config_error = get_public_booking_config_error(website, 'taxi')
        if config_error:
            return Response({'error': config_error}, status=status.HTTP_400_BAD_REQUEST)

        booking = create_public_trip_booking(
            tenant,
            customer_name=data['passenger_name'],
            phone=data['passenger_phone'],
            pickup=data['pickup_address'],
            dropoff=data['dropoff_address'],
            vertical='corporate_shuttle',
            vehicle_type=data['vehicle_type'].lower(),
            cargo_type=f"Passenger trip ({data['passenger_count']} passengers)",
            scheduled_date=data['pickup_time'].date(),
            notes=data.get('notes', ''),
        )
        return Response({
            'success': True,
            'message': 'Your transport request has been saved for operations review.',
            'booking_reference': booking.booking_number,
            'status': booking.status,
        }, status=status.HTTP_201_CREATED)


class PublicBusBookingView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [AnonRateThrottle]

    def post(self, request, tenant_slug):
        tenant, website = resolve_public_tenant(tenant_slug)
        if not tenant or not website or not website.is_published:
            return Response({'error': 'Tenant not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = PublicBusBookingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        config_error = get_public_booking_config_error(website, 'bus')
        if config_error:
            return Response({'error': config_error}, status=status.HTTP_400_BAD_REQUEST)

        booking = create_public_trip_booking(
            tenant,
            customer_name=data['passenger_name'],
            phone=data['passenger_phone'],
            email=data.get('passenger_email', ''),
            pickup=data['boarding_point'],
            dropoff=data['dropping_point'],
            vertical='corporate_shuttle',
            vehicle_type='bus',
            cargo_type=f"Bus seat request ({len(data['seat_numbers'])} seats)",
            notes=f"Trip: {data['trip_id']}\nRequested seats: {', '.join(data['seat_numbers'])}",
        )
        return Response({
            'success': True,
            'message': 'Your seat request has been saved. Seats are not confirmed until operations reviews it.',
            'booking_reference': booking.booking_number,
            'status': booking.status,
        }, status=status.HTTP_201_CREATED)


class PublicTransportRequestView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [AnonRateThrottle]

    def post(self, request, tenant_slug):
        tenant, website = resolve_public_tenant(tenant_slug)
        if not tenant or not website or not website.is_published:
            return Response({'error': 'Tenant not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = PublicTransportRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        config_error = get_public_booking_config_error(website, 'freight')
        if config_error:
            return Response({'error': config_error}, status=status.HTTP_400_BAD_REQUEST)

        booking = create_public_trip_booking(
            tenant,
            customer_name=data['shipper_name'],
            phone=data['shipper_phone'],
            email=data.get('shipper_email', ''),
            pickup=data['origin'],
            dropoff=data['destination'],
            vertical='freight_logistics',
            vehicle_type='heavy_truck',
            cargo_type=data['cargo_type'],
            scheduled_date=data['requested_date'],
            weight_kg=data['weight_tons'] * 1000,
            notes=data.get('notes', ''),
        )
        return Response({
            'success': True,
            'message': 'Your freight request has been saved for operations review.',
            'booking_reference': booking.booking_number,
            'status': booking.status,
        }, status=status.HTTP_201_CREATED)


class PublicShipmentTrackingView(APIView):
    """
    Safe public shipment tracking endpoint.
    Strictly masks PII and omits tenant credentials, financials, and audit logs.
    """
    permission_classes = [AllowAny]
    throttle_classes = [AnonRateThrottle]

    def get(self, request, tracking_number):
        shipment = Shipment.objects.filter(awb_number=tracking_number).first()
        if not shipment:
            return Response({'error': 'Shipment not found with provided tracking code.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = PublicTrackingSerializer(shipment)
        return Response(serializer.data, status=status.HTTP_200_OK)
