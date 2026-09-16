from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from apps.core.viewsets import TenantModelViewSet
from apps.maintenance.models import MaintenanceRecord, MaintenanceSchedule, Breakdown, Accident, RepairOrder
from apps.maintenance.serializers import (
    MaintenanceRecordSerializer,
    MaintenanceScheduleSerializer,
    BreakdownSerializer,
    AccidentSerializer,
    RepairOrderSerializer,
)


class MaintenanceRecordViewSet(TenantModelViewSet):
    queryset = MaintenanceRecord.objects.all().select_related('vehicle')
    serializer_class = MaintenanceRecordSerializer
    required_permission = 'maintenance.view'
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['service_type', 'vehicle']
    ordering_fields = ['performed_date', 'cost']


class MaintenanceScheduleViewSet(TenantModelViewSet):
    queryset = MaintenanceSchedule.objects.all().select_related('vehicle')
    serializer_class = MaintenanceScheduleSerializer
    required_permission = 'maintenance.view'
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['is_active', 'vehicle']
    ordering_fields = ['next_due_date']


class BreakdownViewSet(TenantModelViewSet):
    queryset = Breakdown.objects.all().select_related('vehicle', 'driver')
    serializer_class = BreakdownSerializer
    required_permission = 'maintenance.view'
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['is_resolved', 'vehicle', 'driver']


class AccidentViewSet(TenantModelViewSet):
    queryset = Accident.objects.all().select_related('vehicle', 'driver')
    serializer_class = AccidentSerializer
    required_permission = 'maintenance.view'
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status', 'vehicle', 'driver']


class RepairOrderViewSet(TenantModelViewSet):
    queryset = RepairOrder.objects.all().select_related('vehicle')
    serializer_class = RepairOrderSerializer
    required_permission = 'maintenance.view'
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['status', 'vehicle']
    search_fields = ['order_number', 'issue_summary']
