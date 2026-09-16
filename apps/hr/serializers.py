from rest_framework import serializers
from apps.hr.models import Employee, LeaveRequest, SalaryStructure, Payroll, EmploymentDocument


class EmploymentDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmploymentDocument
        fields = ['id', 'employee', 'title', 'document_type', 'file_path', 'uploaded_at']
        read_only_fields = ['id', 'uploaded_at']


class EmployeeSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    documents = EmploymentDocumentSerializer(many=True, read_only=True)

    class Meta:
        model = Employee
        fields = [
            'id', 'employee_code', 'first_name', 'last_name', 'full_name',
            'email', 'phone', 'department', 'designation', 'date_of_joining',
            'status', 'user', 'documents', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


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
