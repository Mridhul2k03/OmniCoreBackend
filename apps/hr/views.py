from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from apps.core.viewsets import TenantModelViewSet
from apps.hr.models import Employee, LeaveRequest, SalaryStructure, Payroll, PayrollStatus
from apps.hr.serializers import (
    EmployeeSerializer,
    LeaveRequestSerializer,
    SalaryStructureSerializer,
    PayrollSerializer,
)
from apps.audit.services import AuditService


class EmployeeViewSet(TenantModelViewSet):
    queryset = Employee.objects.all().prefetch_related('documents')
    serializer_class = EmployeeSerializer
    required_permission = 'hr.view'
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'department']
    search_fields = ['first_name', 'last_name', 'employee_code', 'email']
    ordering_fields = ['date_of_joining', 'first_name']


class LeaveRequestViewSet(TenantModelViewSet):
    queryset = LeaveRequest.objects.all().select_related('employee')
    serializer_class = LeaveRequestSerializer
    required_permission = 'hr.view'
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status', 'employee']


class SalaryStructureViewSet(TenantModelViewSet):
    queryset = SalaryStructure.objects.all().select_related('employee')
    serializer_class = SalaryStructureSerializer
    required_permission = 'payroll.view'


class PayrollViewSet(TenantModelViewSet):
    queryset = Payroll.objects.all().select_related('employee')
    serializer_class = PayrollSerializer
    required_permission = 'payroll.view'
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['status', 'payroll_month', 'payroll_year', 'employee']
    ordering_fields = ['payroll_year', 'payroll_month']

    @action(detail=True, methods=['post'])
    def mark_paid(self, request, pk=None):
        payroll = self.get_object()
        payroll.status = PayrollStatus.PAID
        from django.utils import timezone
        payroll.payment_date = timezone.now().date()
        payroll.save(update_fields=['status', 'payment_date'])

        AuditService.record(
            action='PAYROLL_PAID',
            actor=request.user,
            tenant=request.tenant,
            target_type='Payroll',
            target_id=str(payroll.id),
            after_snapshot={'employee': payroll.employee.full_name, 'net_pay': str(payroll.net_pay)}
        )
        return Response({'message': f"Payroll for {payroll.employee.full_name} marked as PAID."})
