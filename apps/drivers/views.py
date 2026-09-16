from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from apps.core.viewsets import TenantModelViewSet
from apps.drivers.models import Driver, DriverDocument, DriverAssignment, Attendance, DriverIncident, DriverStatus
from apps.drivers.serializers import (
    DriverSerializer,
    DriverDocumentSerializer,
    AttendanceSerializer,
    DriverIncidentSerializer,
)
from apps.core.exceptions import BusinessValidationError
from apps.audit.services import AuditService


class DriverViewSet(TenantModelViewSet):
    queryset = Driver.objects.all().select_related('current_vehicle').prefetch_related('documents')
    serializer_class = DriverSerializer
    required_permission = 'driver.view'
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'license_type']
    search_fields = ['first_name', 'last_name', 'license_number', 'phone']
    ordering_fields = ['created_at', 'license_expiry', 'first_name']

    def perform_create(self, serializer):
        super().perform_create(serializer)
        AuditService.record(
            action='DRIVER_CREATED',
            actor=self.request.user,
            tenant=self.request.tenant,
            target_type='Driver',
            target_id=str(serializer.instance.id),
            after_snapshot={'name': serializer.instance.full_name, 'license': serializer.instance.license_number}
        )

    @action(detail=True, methods=['post'])
    def assign_vehicle(self, request, pk=None):
        driver = self.get_object()
        vehicle_id = request.data.get('vehicle_id')
        from apps.fleet.models import Vehicle, VehicleAssignment
        from django.utils import timezone

        if vehicle_id:
            vehicle = Vehicle.objects.filter(id=vehicle_id, tenant=request.tenant).first()
            if not vehicle:
                raise BusinessValidationError("Vehicle not found in your tenant scope.")
            driver.current_vehicle = vehicle
            driver.save(update_fields=['current_vehicle'])

            # Log assignment
            VehicleAssignment.objects.create(
                tenant=request.tenant,
                vehicle=vehicle,
                driver=driver,
                assigned_from=timezone.now(),
                is_active=True
            )
            return Response({'message': f"Vehicle {vehicle.registration_number} assigned to {driver.full_name}."})
        else:
            driver.current_vehicle = None
            driver.save(update_fields=['current_vehicle'])
            return Response({'message': f"Vehicle unassigned from {driver.full_name}."})


class DriverDocumentViewSet(TenantModelViewSet):
    queryset = DriverDocument.objects.all().select_related('driver')
    serializer_class = DriverDocumentSerializer
    required_permission = 'driver.view'
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['document_type', 'is_verified', 'driver']
    search_fields = ['document_number']


class AttendanceViewSet(TenantModelViewSet):
    queryset = Attendance.objects.all().select_related('driver')
    serializer_class = AttendanceSerializer
    required_permission = 'driver.view'
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'date', 'driver']
    ordering_fields = ['date']


class DriverIncidentViewSet(TenantModelViewSet):
    queryset = DriverIncident.objects.all().select_related('driver', 'vehicle')
    serializer_class = DriverIncidentSerializer
    required_permission = 'driver.view'
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['severity', 'driver', 'vehicle']
    ordering_fields = ['incident_date']
