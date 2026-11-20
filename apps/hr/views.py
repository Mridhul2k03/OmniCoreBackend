from rest_framework import status
from rest_framework import permissions
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView
from rest_framework.decorators import action
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from django.db import transaction
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from apps.core.viewsets import TenantModelViewSet
from apps.hr.models import Employee, EmployeeInvitation, LeaveRequest, SalaryStructure, Payroll, PayrollStatus
from apps.hr.serializers import (
    EmployeeSerializer,
    EmployeeInvitationSerializer,
    EmployeeAccessSerializer,
    LeaveRequestSerializer,
    SalaryStructureSerializer,
    PayrollSerializer,
)
from apps.audit.services import AuditService
from apps.core.exceptions import BusinessValidationError, PermissionDeniedError
from apps.hr.invitations import (
    accept_employee_invitation,
    create_employee_invitation,
    get_invitation,
    resend_employee_invitation,
)
from apps.tenants.models import TenantUser

User = get_user_model()


class EmployeeViewSet(TenantModelViewSet):
    queryset = Employee.objects.all().select_related('user').prefetch_related('documents', 'invitation__role')
    serializer_class = EmployeeSerializer
    required_permission = 'hr.view'
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'department']
    search_fields = ['first_name', 'last_name', 'employee_code', 'email']
    ordering_fields = ['date_of_joining', 'first_name']

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if self.action in {'create', 'update', 'partial_update', 'destroy', 'invite', 'resend_invitation', 'update_access'}:
            self._require_primary_admin()

    def get_permissions(self):
        if self.action in {'create', 'update', 'partial_update', 'destroy', 'invite', 'resend_invitation', 'update_access'}:
            self.required_permission = 'tenant.manage'
        else:
            self.required_permission = 'hr.view'
        return super().get_permissions()

    def _require_primary_admin(self):
        membership = getattr(self.request, 'tenant_user', None)
        if not membership or not membership.is_primary or not membership.role or membership.role.code != 'TENANT_ADMIN':
            raise PermissionDeniedError(
                detail='Only the primary tenant administrator can invite employees and assign their roles.',
                code='PRIMARY_ADMIN_REQUIRED',
            )

    def create(self, request, *args, **kwargs):
        return Response(
            {
                'code': 'INVITATION_REQUIRED',
                'message': 'Employees must be created through the invitation flow so they can activate their own login.',
            },
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    @action(detail=False, methods=['post'], url_path='invite')
    def invite(self, request):
        self._require_primary_admin()
        serializer = EmployeeInvitationSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        result = create_employee_invitation(tenant=request.tenant, invited_by=request.user, data=serializer.validated_data)
        response_data = {
            'employee': EmployeeSerializer(result['employee'], context=self.get_serializer_context()).data,
            'message': f"Invitation sent to {result['employee'].email}.",
        }
        if result.get('invitation_url'):
            response_data['invitation_url'] = result['invitation_url']
        return Response(response_data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='resend-invitation')
    def resend_invitation(self, request, pk=None):
        self._require_primary_admin()
        employee = self.get_object()
        result = resend_employee_invitation(employee=employee, invited_by=request.user)
        employee.refresh_from_db()
        response_data = {
            'employee': EmployeeSerializer(employee, context=self.get_serializer_context()).data,
            'message': f"Invitation resent to {result['employee'].email}.",
        }
        if result.get('invitation_url'):
            response_data['invitation_url'] = result['invitation_url']
        return Response(response_data)

    @action(detail=True, methods=['patch'], url_path='access')
    def update_access(self, request, pk=None):
        self._require_primary_admin()
        employee = self.get_object()
        serializer = EmployeeAccessSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        result = None

        with transaction.atomic():
            if employee.user_id:
                membership = TenantUser.objects.select_for_update().filter(tenant=request.tenant, user=employee.user).first()
                if not membership:
                    raise BusinessValidationError('The employee account has no membership in this organization.')
                if membership.is_primary:
                    raise PermissionDeniedError('The primary administrator access cannot be changed here.', code='PRIMARY_ADMIN_REQUIRED')
                if 'role' in data:
                    membership.role = data['role']
                if 'is_active' in data:
                    membership.is_active = data['is_active']
                membership.save(update_fields=['role', 'is_active', 'updated_at'])
            else:
                invitation = EmployeeInvitation.objects.select_for_update().filter(employee=employee).first()
                if not invitation:
                    raise BusinessValidationError('This employee has no invitation or linked account.')
                if 'role' in data:
                    invitation.role = data['role']
                if data.get('is_active') is False:
                    invitation.status = EmployeeInvitation.Status.REVOKED
                    invitation.save(update_fields=['role', 'status', 'updated_at'])
                elif data.get('is_active') is True and (
                    invitation.status in {EmployeeInvitation.Status.REVOKED, EmployeeInvitation.Status.EXPIRED}
                    or invitation.is_expired
                ):
                    invitation.save(update_fields=['role', 'updated_at'])
                    result = resend_employee_invitation(employee=employee, invited_by=request.user)
                else:
                    invitation.save(update_fields=['role', 'updated_at'])

            AuditService.record(
                action='EMPLOYEE_ACCESS_UPDATED',
                actor=request.user,
                tenant=request.tenant,
                target_type='Employee',
                target_id=str(employee.id),
                after_snapshot={
                    'role': data['role'].code if 'role' in data else None,
                    'is_active': data.get('is_active'),
                },
            )

        employee.refresh_from_db()
        response_data = {
            'employee': EmployeeSerializer(employee, context=self.get_serializer_context()).data,
            'message': 'Employee access updated successfully.',
        }
        if result and result.get('invitation_url'):
            response_data['invitation_url'] = result['invitation_url']
        return Response(response_data)


class EmployeeInvitationAcceptView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [AnonRateThrottle]

    def get(self, request):
        invitation = get_invitation(request.query_params.get('token'))
        user = TenantUser.objects.filter(tenant=invitation.tenant, user__email__iexact=invitation.employee.email).first()
        if user and user.is_active:
            raise BusinessValidationError('This account already has active access to the organization.')
        existing_account = invitation.employee.user or User.objects.filter(email__iexact=invitation.employee.email).first()
        return Response({
            'email': invitation.employee.email,
            'first_name': invitation.employee.first_name,
            'last_name': invitation.employee.last_name,
            'company_name': invitation.tenant.company_name,
            'role_name': invitation.role.name,
            'requires_password': not existing_account or not existing_account.has_usable_password(),
        })

    def post(self, request):
        token = request.data.get('token')
        new_password = request.data.get('new_password')
        if new_password is not None and not isinstance(new_password, str):
            raise BusinessValidationError('new_password must be a string.', fields={'new_password': ['Enter a valid password.']})
        user, invitation = accept_employee_invitation(token=token, new_password=new_password)
        return Response({
            'message': 'Your account is ready. Sign in with your email and password.',
            'email': user.email,
            'company_name': invitation.tenant.company_name,
        })


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
