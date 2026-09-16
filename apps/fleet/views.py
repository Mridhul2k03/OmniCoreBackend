from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from apps.core.viewsets import TenantModelViewSet
from apps.fleet.models import Vehicle, VehicleCategory, VehicleDocument, VehicleAssignment, VehicleStatus
from apps.fleet.serializers import (
    VehicleSerializer,
    VehicleCategorySerializer,
    VehicleDocumentSerializer,
    VehicleAssignmentSerializer,
)
from apps.core.exceptions import BusinessValidationError
from apps.audit.services import AuditService


class VehicleCategoryViewSet(TenantModelViewSet):
    queryset = VehicleCategory.objects.all()
    serializer_class = VehicleCategorySerializer
    required_permission = 'vehicle.view'


class VehicleViewSet(TenantModelViewSet):
    queryset = Vehicle.objects.all().select_related('category').prefetch_related('documents')
    serializer_class = VehicleSerializer
    required_permission = 'vehicle.view'
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'availability', 'ownership', 'category', 'fuel_type']
    search_fields = ['registration_number', 'make', 'model', 'vin_number']
    ordering_fields = ['created_at', 'registration_number', 'odometer']

    def perform_create(self, serializer):
        # RBAC check for creation
        from apps.core.permissions import HasPermission
        super().perform_create(serializer)
        AuditService.record(
            action='VEHICLE_CREATED',
            actor=self.request.user,
            tenant=self.request.tenant,
            target_type='Vehicle',
            target_id=str(serializer.instance.id),
            after_snapshot={'registration_number': serializer.instance.registration_number}
        )

    @action(detail=True, methods=['post'])
    def update_odometer(self, request, pk=None):
        vehicle = self.get_object()
        new_odometer = request.data.get('odometer')
        if new_odometer is None:
            raise BusinessValidationError("A valid 'odometer' value is required.")
        try:
            val = float(new_odometer)
            if val < float(vehicle.odometer):
                raise BusinessValidationError("New odometer reading cannot be less than the current reading.")
            vehicle.odometer = val
            vehicle.save(update_fields=['odometer'])
            return Response({'message': 'Odometer reading updated.', 'odometer': vehicle.odometer})
        except ValueError:
            raise BusinessValidationError("Invalid odometer number.")

    @action(detail=True, methods=['post'])
    def change_status(self, request, pk=None):
        vehicle = self.get_object()
        new_status = request.data.get('status')
        if new_status not in VehicleStatus.values:
            raise BusinessValidationError(f"Invalid vehicle status '{new_status}'.")
        old_status = vehicle.status
        vehicle.status = new_status
        vehicle.save(update_fields=['status'])
        AuditService.record(
            action='VEHICLE_STATUS_CHANGED',
            actor=request.user,
            tenant=request.tenant,
            target_type='Vehicle',
            target_id=str(vehicle.id),
            before_snapshot={'status': old_status},
            after_snapshot={'status': new_status}
        )
        return Response({'message': f"Vehicle status updated to {new_status}."})


class VehicleDocumentViewSet(TenantModelViewSet):
    queryset = VehicleDocument.objects.all().select_related('vehicle')
    serializer_class = VehicleDocumentSerializer
    required_permission = 'vehicle.view'
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['document_type', 'status', 'vehicle']
    search_fields = ['document_number']
