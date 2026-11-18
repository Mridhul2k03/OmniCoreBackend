from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import transaction
from django.utils.dateparse import parse_date
from django.utils import timezone
from apps.core.viewsets import TenantModelViewSet
from apps.core.middleware import resolve_tenant_context

from apps.shuttle.models import (
    ShuttleOrganization, ShuttleRoute, ShuttleStop, ShuttleSchedule,
    PassengerProfile, ShuttleAssignment, ShuttleTrip, ShuttleAttendance
)
from apps.shuttle.serializers import (
    ShuttleOrganizationSerializer, ShuttleRouteSerializer, ShuttleStopSerializer,
    ShuttleScheduleSerializer, PassengerProfileSerializer,
    ShuttleAssignmentSerializer, ShuttleTripSerializer, ShuttleAttendanceSerializer
)
from apps.shuttle.services import ShuttleOperationService


class ShuttleOrganizationViewSet(TenantModelViewSet):
    queryset = ShuttleOrganization.objects.all()
    serializer_class = ShuttleOrganizationSerializer
    search_fields = ['name', 'code', 'contact_person', 'contact_email']
    filterset_fields = ['org_type', 'is_active']


class ShuttleRouteViewSet(TenantModelViewSet):
    queryset = ShuttleRoute.objects.select_related('organization', 'base_route', 'default_vehicle', 'default_driver').prefetch_related('stops').all()
    serializer_class = ShuttleRouteSerializer
    search_fields = ['route_name', 'route_code', 'start_location', 'end_location']
    filterset_fields = ['organization', 'direction', 'is_active']


class ShuttleStopViewSet(TenantModelViewSet):
    queryset = ShuttleStop.objects.select_related('shuttle_route').all()
    serializer_class = ShuttleStopSerializer
    filterset_fields = ['shuttle_route']


class ShuttleScheduleViewSet(TenantModelViewSet):
    queryset = ShuttleSchedule.objects.select_related('shuttle_route', 'vehicle', 'driver').all()
    serializer_class = ShuttleScheduleSerializer
    filterset_fields = ['shuttle_route', 'day_of_week', 'is_active']

    @action(detail=True, methods=['post'], url_path='generate-trip')
    def generate_trip(self, request, pk=None):
        schedule = self.get_object()
        trip_date = parse_date(str(request.data.get('trip_date', '')))
        if not trip_date:
            return Response({'trip_date': ['Provide a valid trip date (YYYY-MM-DD).']}, status=status.HTTP_400_BAD_REQUEST)
        if not schedule.is_active:
            return Response({'schedule': ['An inactive schedule cannot generate a trip.']}, status=status.HTTP_400_BAD_REQUEST)
        weekday_code = ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN'][trip_date.weekday()]
        schedule_days = str(schedule.day_of_week).upper()
        if schedule_days not in ['ALL', weekday_code] and not (schedule_days == 'WEEKDAYS' and trip_date.weekday() < 5):
            return Response({'trip_date': [f'The selected schedule does not run on {weekday_code}.']}, status=status.HTTP_400_BAD_REQUEST)
        existing_trip = ShuttleTrip.objects.filter(tenant=schedule.tenant, schedule=schedule, trip_date=trip_date).first()
        if existing_trip:
            return Response(ShuttleTripSerializer(existing_trip).data, status=status.HTTP_200_OK)
        trip = ShuttleOperationService.generate_daily_trip(
            route=schedule.shuttle_route, schedule=schedule, trip_date=trip_date,
        )
        return Response(ShuttleTripSerializer(trip).data, status=status.HTTP_201_CREATED)


class PassengerProfileViewSet(TenantModelViewSet):
    queryset = PassengerProfile.objects.select_related('organization', 'pickup_stop', 'dropoff_stop').all()
    serializer_class = PassengerProfileSerializer
    search_fields = ['first_name', 'last_name', 'id_number', 'email', 'phone']
    filterset_fields = ['organization', 'passenger_type', 'is_active']

    @action(detail=False, methods=['post'], url_path='enroll')
    def enroll(self, request):
        tenant, _ = resolve_tenant_context(request)
        organization = ShuttleOrganization.objects.filter(tenant=tenant, id=request.data.get('organization')).first()
        route = ShuttleRoute.objects.filter(
            tenant=tenant, id=request.data.get('shuttle_route'), organization=organization,
        ).first() if organization else None
        if not organization:
            return Response({'organization': ['Select an organization in this workspace.']}, status=status.HTTP_400_BAD_REQUEST)
        if not route:
            return Response({'shuttle_route': ['Select a route belonging to this organization.']}, status=status.HTTP_400_BAD_REQUEST)

        passenger_data = {
            key: request.data.get(key) for key in [
                'passenger_type', 'first_name', 'last_name', 'id_number', 'email', 'phone',
                'pickup_stop', 'dropoff_stop', 'emergency_contact_name', 'emergency_contact_phone',
            ]
        }
        serializer = PassengerProfileSerializer(data={**passenger_data, 'organization': str(organization.id)}, context=self.get_serializer_context())
        serializer.is_valid(raise_exception=True)
        if PassengerProfile.objects.filter(tenant=tenant, organization=organization, id_number=str(request.data.get('id_number', '')).strip()).exists():
            return Response({'id_number': ['A passenger with this ID is already registered for this organization.']}, status=status.HTTP_400_BAD_REQUEST)
        effective_from = parse_date(str(request.data.get('effective_from') or timezone.localdate().isoformat()))
        if not effective_from:
            return Response({'effective_from': ['Provide a valid effective date (YYYY-MM-DD).']}, status=status.HTTP_400_BAD_REQUEST)
        for stop_field in ('pickup_stop', 'dropoff_stop'):
            stop_id = passenger_data.get(stop_field)
            if stop_id and not ShuttleStop.objects.filter(tenant=tenant, id=stop_id, shuttle_route=route).exists():
                return Response({stop_field: ['Choose a stop on the selected route.']}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            passenger = serializer.save(tenant=tenant)
            assignment = ShuttleAssignment.objects.create(
                tenant=tenant, passenger=passenger, shuttle_route=route,
                seat_number=str(request.data.get('seat_number', '')).strip(), effective_from=effective_from,
            )
        return Response({
            'passenger': PassengerProfileSerializer(passenger, context=self.get_serializer_context()).data,
            'assignment': ShuttleAssignmentSerializer(assignment, context=self.get_serializer_context()).data,
        }, status=status.HTTP_201_CREATED)


class ShuttleAssignmentViewSet(TenantModelViewSet):
    queryset = ShuttleAssignment.objects.select_related('passenger', 'shuttle_route').all()
    serializer_class = ShuttleAssignmentSerializer
    filterset_fields = ['passenger', 'shuttle_route', 'is_active']


class ShuttleAttendanceViewSet(TenantModelViewSet):
    queryset = ShuttleAttendance.objects.select_related('shuttle_trip', 'passenger', 'shuttle_stop', 'verified_by').all()
    serializer_class = ShuttleAttendanceSerializer
    filterset_fields = ['shuttle_trip', 'passenger', 'status']


class ShuttleTripViewSet(TenantModelViewSet):
    queryset = ShuttleTrip.objects.select_related('shuttle_route', 'vehicle', 'driver', 'schedule').prefetch_related('attendance_records').all()
    serializer_class = ShuttleTripSerializer
    search_fields = ['trip_number', 'shuttle_route__route_code', 'shuttle_route__route_name']
    filterset_fields = ['shuttle_route', 'trip_date', 'status']

    @action(detail=True, methods=['post'], url_path='start')
    def start(self, request, pk=None):
        trip = self.get_object()
        notes = request.data.get('notes', '')
        trip = ShuttleOperationService.start_trip(trip, actor=request.user, notes=notes)
        return Response(ShuttleTripSerializer(trip).data)

    @action(detail=True, methods=['post'], url_path='complete')
    def complete(self, request, pk=None):
        trip = self.get_object()
        notes = request.data.get('notes', '')
        trip = ShuttleOperationService.complete_trip(trip, actor=request.user, notes=notes)
        return Response(ShuttleTripSerializer(trip).data)

    @action(detail=True, methods=['post'], url_path='attendance')
    def mark_attendance(self, request, pk=None):
        trip = self.get_object()
        tenant, _ = resolve_tenant_context(request)
        passenger_id = request.data.get('passenger_id')
        attendance_status = request.data.get('status', 'BOARDED')
        stop_id = request.data.get('stop_id')
        notes = request.data.get('notes', '')

        passenger = PassengerProfile.objects.filter(tenant=tenant, id=passenger_id, is_active=True).first()
        if not passenger:
            return Response({'error': 'Passenger not found in tenant'}, status=status.HTTP_404_NOT_FOUND)
        if not passenger.route_assignments.filter(tenant=tenant, shuttle_route=trip.shuttle_route, is_active=True).exists():
            return Response({'passenger_id': ['Passenger is not actively assigned to this trip route.']}, status=status.HTTP_400_BAD_REQUEST)

        stop = None
        if stop_id:
            stop = ShuttleStop.objects.filter(tenant=tenant, id=stop_id, shuttle_route=trip.shuttle_route).first()
            if not stop:
                return Response({'stop_id': ['Select a stop on this trip route.']}, status=status.HTTP_400_BAD_REQUEST)

        attendance = ShuttleOperationService.record_attendance(
            trip=trip,
            passenger=passenger,
            status=attendance_status,
            stop=stop,
            verified_by=request.user,
            notes=notes
        )
        return Response(ShuttleAttendanceSerializer(attendance).data, status=status.HTTP_200_OK)
