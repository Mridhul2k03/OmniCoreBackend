from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from apps.core.viewsets import TenantModelViewSet
from apps.trips.models import Booking, Route, Trip, TripExpense, TripStatus
from apps.trips.serializers import BookingSerializer, RouteSerializer, TripSerializer, TripExpenseSerializer
from apps.trips.services import TripWorkflowService
from apps.core.exceptions import BusinessValidationError


class BookingViewSet(TenantModelViewSet):
    queryset = Booking.objects.all().select_related('customer')
    serializer_class = BookingSerializer
    required_permission = 'trip.view'
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'scheduled_date', 'customer']
    search_fields = ['booking_number', 'pickup_location', 'dropoff_location']
    ordering_fields = ['scheduled_date', 'created_at']


class RouteViewSet(TenantModelViewSet):
    queryset = Route.objects.all()
    serializer_class = RouteSerializer
    required_permission = 'trip.view'
    search_fields = ['name', 'origin', 'destination']


class TripViewSet(TenantModelViewSet):
    queryset = Trip.objects.all().select_related('customer', 'vehicle', 'driver', 'route').prefetch_related('expenses')
    serializer_class = TripSerializer
    required_permission = 'trip.view'
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'customer', 'vehicle', 'driver']
    search_fields = ['trip_number', 'origin', 'destination']
    ordering_fields = ['created_at', 'actual_start', 'distance_km']

    @action(detail=True, methods=['post'])
    def dispatch_trip(self, request, pk=None):
        trip = self.get_object()
        updated = TripWorkflowService.transition(
            trip=trip,
            target_status=TripStatus.DISPATCHED,
            actor=request.user
        )
        return Response({'message': f"Trip {trip.trip_number} successfully dispatched.", 'status': updated.status})

    @action(detail=True, methods=['post'])
    def start_trip(self, request, pk=None):
        trip = self.get_object()
        updated = TripWorkflowService.transition(
            trip=trip,
            target_status=TripStatus.STARTED,
            actor=request.user,
            extra_data={'start_odometer': request.data.get('start_odometer')}
        )
        return Response({'message': f"Trip {trip.trip_number} started.", 'status': updated.status})

    @action(detail=True, methods=['post'])
    def complete_trip(self, request, pk=None):
        trip = self.get_object()
        end_odometer = request.data.get('end_odometer')
        if not end_odometer:
            raise BusinessValidationError("An 'end_odometer' reading is required to complete a trip.")
        updated = TripWorkflowService.transition(
            trip=trip,
            target_status=TripStatus.COMPLETED,
            actor=request.user,
            extra_data={'end_odometer': end_odometer}
        )
        return Response({'message': f"Trip {trip.trip_number} completed. Ready for billing.", 'status': updated.status})

    @action(detail=True, methods=['post'])
    def cancel_trip(self, request, pk=None):
        trip = self.get_object()
        updated = TripWorkflowService.transition(
            trip=trip,
            target_status=TripStatus.CANCELLED,
            actor=request.user,
            extra_data={'reason': request.data.get('reason', '')}
        )
        return Response({'message': f"Trip {trip.trip_number} cancelled.", 'status': updated.status})


class TripExpenseViewSet(TenantModelViewSet):
    queryset = TripExpense.objects.all().select_related('trip')
    serializer_class = TripExpenseSerializer
    required_permission = 'trip.view'
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['trip', 'expense_type', 'is_approved']
