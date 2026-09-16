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
    PublicBusBookingSerializer, PublicTransportRequestSerializer
)
from apps.courier.models import Shipment, ShipmentStatus
from apps.courier.serializers import PublicTrackingSerializer
from apps.courier.services import generate_awb


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
        return Response(serializer.data, status=status.HTTP_200_OK)


class PublicCourierBookingView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [AnonRateThrottle]

    def post(self, request, tenant_slug):
        tenant, _ = resolve_public_tenant(tenant_slug)
        if not tenant:
            return Response({'error': 'Tenant not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = PublicCourierBookingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

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
        tenant, _ = resolve_public_tenant(tenant_slug)
        if not tenant:
            return Response({'error': 'Tenant not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = PublicTaxiBookingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        return Response({
            'success': True,
            'message': 'Taxi ride requested successfully. Dispatch is pending.',
            'booking_reference': f"TXI-{tenant.id.hex[:6].upper()}",
            'pickup': data['pickup_address'],
            'dropoff': data['dropoff_address']
        }, status=status.HTTP_201_CREATED)


class PublicBusBookingView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [AnonRateThrottle]

    def post(self, request, tenant_slug):
        tenant, _ = resolve_public_tenant(tenant_slug)
        if not tenant:
            return Response({'error': 'Tenant not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = PublicBusBookingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        return Response({
            'success': True,
            'message': 'Bus seat reservation submitted.',
            'ticket_reference': f"BUS-TKT-{tenant.id.hex[:6].upper()}",
            'seats': data['seat_numbers']
        }, status=status.HTTP_201_CREATED)


class PublicTransportRequestView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [AnonRateThrottle]

    def post(self, request, tenant_slug):
        tenant, _ = resolve_public_tenant(tenant_slug)
        if not tenant:
            return Response({'error': 'Tenant not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = PublicTransportRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        return Response({
            'success': True,
            'message': 'Freight transport request received. Commercial quote will follow.',
            'quote_request_id': f"TRP-{tenant.id.hex[:6].upper()}",
            'cargo_type': data['cargo_type']
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
