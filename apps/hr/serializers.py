from rest_framework import serializers
from apps.hr.models import Employee, EmployeeInvitation, LeaveRequest, SalaryStructure, Payroll, EmploymentDocument
from apps.tenants.models import Role, TenantUser


class EmploymentDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmploymentDocument
        fields = ['id', 'employee', 'title', 'document_type', 'file_path', 'uploaded_at']
        read_only_fields = ['id', 'uploaded_at']


class EmployeeSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    documents = EmploymentDocumentSerializer(many=True, read_only=True)
    role = serializers.SerializerMethodField()
    role_id = serializers.SerializerMethodField()
    account_status = serializers.SerializerMethodField()

    class Meta:
        model = Employee
        fields = [
            'id', 'employee_code', 'first_name', 'last_name', 'full_name',
            'email', 'phone', 'department', 'designation', 'date_of_joining',
            'status', 'user', 'role', 'role_id', 'account_status', 'documents', 'created_at'
        ]
        read_only_fields = ['id', 'created_at', 'employee_code', 'email', 'user']

    def get_role(self, obj):
        if obj.user_id:
            membership = TenantUser.objects.filter(tenant=obj.tenant, user=obj.user).select_related('role').first()
            if membership and membership.role:
                return membership.role.name
        try:
            invitation = obj.invitation
            if invitation.status == invitation.Status.PENDING and invitation.is_expired:
                return invitation.role.name
            return invitation.role.name
        except EmployeeInvitation.DoesNotExist:
            return 'Unassigned'

    def get_role_id(self, obj):
        if obj.user_id:
            membership = TenantUser.objects.filter(tenant=obj.tenant, user=obj.user).first()
            if membership and membership.role_id:
                return str(membership.role_id)
        try:
            return str(obj.invitation.role_id)
        except EmployeeInvitation.DoesNotExist:
            return None

    def get_account_status(self, obj):
        if obj.user_id:
            membership = TenantUser.objects.filter(tenant=obj.tenant, user=obj.user).first()
            return 'active' if membership and membership.is_active else 'inactive'
        try:
            invitation = obj.invitation
        except EmployeeInvitation.DoesNotExist:
            return 'not_invited'
        if invitation.status == invitation.Status.PENDING and invitation.is_expired:
            return 'expired'
        return invitation.status.lower()


class EmployeeInvitationSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=100)
    last_name = serializers.CharField(max_length=100)
    email = serializers.EmailField()
    phone = serializers.CharField(max_length=30, required=False, allow_blank=True)
    department = serializers.CharField(max_length=100, required=False, default='OPERATIONS')
    designation = serializers.CharField(max_length=100)
    date_of_joining = serializers.DateField()
    role = serializers.PrimaryKeyRelatedField(queryset=Role.objects.all())

    def validate_email(self, value):
        return value.strip().lower()

    def validate_role(self, role):
        tenant = self.context['request'].tenant
        if role.tenant_id not in (None, tenant.id):
            raise serializers.ValidationError('Choose a role available to this tenant.')
        if role.code == 'TENANT_ADMIN':
            raise serializers.ValidationError('The primary tenant administrator role cannot be assigned to employees.')
        return role

    def validate_department(self, value):
        return value.strip().upper()


class EmployeeAccessSerializer(serializers.Serializer):
    role = serializers.PrimaryKeyRelatedField(queryset=Role.objects.all(), required=False)
    is_active = serializers.BooleanField(required=False)

    def validate_role(self, role):
        tenant = self.context['request'].tenant
        if role.tenant_id not in (None, tenant.id):
            raise serializers.ValidationError('Choose a role available to this tenant.')
        if role.code == 'TENANT_ADMIN':
            raise serializers.ValidationError('The primary administrator role cannot be assigned to employees.')
        return role

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError('Provide a role and/or access status to update.')
        return attrs


class LeaveRequestSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)

    class Meta:
        model = LeaveRequest
        fields = ['id', 'employee', 'employee_name', 'leave_type', 'start_date', 'end_date', 'reason', 'status', 'approved_by', 'created_at']
        read_only_fields = ['id', 'created_at']


class SalaryStructureSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)

    class Meta:
        model = SalaryStructure
        fields = ['id', 'employee', 'employee_name', 'basic_salary', 'allowances', 'deductions', 'net_salary']
        read_only_fields = ['id', 'net_salary']


class PayrollSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)

    class Meta:
        model = Payroll
        fields = [
            'id', 'payroll_month', 'payroll_year', 'employee', 'employee_name',
            'basic_pay', 'allowances', 'deductions', 'net_pay', 'status', 'payment_date'
        ]
        read_only_fields = ['id', 'net_pay']
