import django_filters
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from apps.core.viewsets import TenantModelViewSet
from apps.fleet.models import (
    Vehicle,
    VehicleCategory,
    VehicleDocument,
    VehicleAssignment,
    VehicleStatus,
    Branch,
)
from apps.fleet.serializers import (
    VehicleSerializer,
    VehicleCategorySerializer,
    VehicleDocumentSerializer,
    VehicleAssignmentSerializer,
    BranchSerializer,
)
from apps.core.exceptions import BusinessValidationError
from apps.audit.services import AuditService


class BranchViewSet(TenantModelViewSet):
    queryset = Branch.objects.all()
    serializer_class = BranchSerializer
    required_permission = 'vehicle.view'
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['is_active', 'city', 'state']
    search_fields = ['name', 'code', 'city', 'state']
    ordering_fields = ['name', 'created_at']


class VehicleCategoryViewSet(TenantModelViewSet):
    queryset = VehicleCategory.objects.all()
    serializer_class = VehicleCategorySerializer
    required_permission = 'vehicle.view'


class VehicleFilter(django_filters.FilterSet):
    status = django_filters.CharFilter(method='filter_status')
    vertical = django_filters.CharFilter(method='filter_vertical')

    class Meta:
        model = Vehicle
        fields = [
            'status', 'availability', 'ownership', 'category',
            'fuel_type', 'vertical', 'type', 'branch', 'assigned_driver'
        ]

    def filter_status(self, queryset, name, value):
        if not value or str(value).lower() == 'all':
            return queryset
        return queryset.filter(status__iexact=value)

    def filter_vertical(self, queryset, name, value):
        if not value or str(value).lower() == 'all':
            return queryset
        return queryset.filter(vertical__iexact=value)


class VehicleViewSet(TenantModelViewSet):
    queryset = Vehicle.objects.all().select_related('category', 'branch', 'assigned_driver').prefetch_related('documents')
    serializer_class = VehicleSerializer
    required_permission = 'vehicle.view'
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = VehicleFilter
    search_fields = ['registration_number', 'make', 'model', 'vin', 'assigned_driver__first_name', 'assigned_driver__last_name']
    ordering_fields = ['created_at', 'registration_number', 'odometer_km']

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
        new_odometer = request.data.get('odometer_km') if request.data.get('odometer_km') is not None else request.data.get('odometer')
        if new_odometer is None:
            raise BusinessValidationError("A valid 'odometer_km' or 'odometer' value is required.")
        try:
            val = float(new_odometer)
            if val < float(vehicle.odometer_km):
                raise BusinessValidationError("New odometer reading cannot be less than the current reading.")
            vehicle.odometer_km = val
            vehicle.save(update_fields=['odometer_km'])
            return Response({
                'message': 'Odometer reading updated.',
                'odometer_km': vehicle.odometer_km,
                'odometer': vehicle.odometer_km,
            })
        except ValueError:
            raise BusinessValidationError("Invalid odometer number.")

    @action(detail=True, methods=['post'])
    def change_status(self, request, pk=None):
        vehicle = self.get_object()
        new_status = request.data.get('status')
        # Case-insensitive match against VehicleStatus values
        valid_statuses = {v.lower(): v for v in VehicleStatus.values}
        if not new_status or str(new_status).lower() not in valid_statuses:
            raise BusinessValidationError(f"Invalid vehicle status '{new_status}'.")
        matched_status = valid_statuses[str(new_status).lower()]
        old_status = vehicle.status
        vehicle.status = matched_status
        vehicle.save(update_fields=['status'])
        AuditService.record(
            action='VEHICLE_STATUS_CHANGED',
            actor=request.user,
            tenant=request.tenant,
            target_type='Vehicle',
            target_id=str(vehicle.id),
            before_snapshot={'status': old_status},
            after_snapshot={'status': matched_status}
        )
        return Response({'message': f"Vehicle status updated to {matched_status}."})


class VehicleDocumentViewSet(TenantModelViewSet):
    queryset = VehicleDocument.objects.all().select_related('vehicle')
    serializer_class = VehicleDocumentSerializer
    required_permission = 'vehicle.view'
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['document_type', 'status', 'vehicle']
    search_fields = ['document_number']
