from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from apps.core.viewsets import TenantModelViewSet

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


class PassengerProfileViewSet(TenantModelViewSet):
    queryset = PassengerProfile.objects.select_related('organization', 'pickup_stop', 'dropoff_stop').all()
    serializer_class = PassengerProfileSerializer
    search_fields = ['first_name', 'last_name', 'id_number', 'email', 'phone']
    filterset_fields = ['organization', 'passenger_type', 'is_active']


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
        passenger_id = request.data.get('passenger_id')
        attendance_status = request.data.get('status', 'BOARDED')
        stop_id = request.data.get('stop_id')
        notes = request.data.get('notes', '')

        passenger = PassengerProfile.objects.filter(tenant=self.tenant, id=passenger_id).first()
        if not passenger:
            return Response({'error': 'Passenger not found in tenant'}, status=status.HTTP_404_NOT_FOUND)

        stop = None
        if stop_id:
            stop = ShuttleStop.objects.filter(tenant=self.tenant, id=stop_id).first()

        attendance = ShuttleOperationService.record_attendance(
            trip=trip,
            passenger=passenger,
            status=attendance_status,
            stop=stop,
            verified_by=request.user,
            notes=notes
        )
        return Response(ShuttleAttendanceSerializer(attendance).data, status=status.HTTP_200_OK)
