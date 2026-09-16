import uuid
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from apps.core.models import TenantOwnedModel


class EmployeeStatus(models.TextChoices):
    ACTIVE = 'ACTIVE', _('Active')
    ON_LEAVE = 'ON_LEAVE', _('On Leave')
    PROBATION = 'PROBATION', _('Probation')
    TERMINATED = 'TERMINATED', _('Terminated')


class LeaveStatus(models.TextChoices):
    PENDING = 'PENDING', _('Pending Approval')
    APPROVED = 'APPROVED', _('Approved')
    REJECTED = 'REJECTED', _('Rejected')


class PayrollStatus(models.TextChoices):
    DRAFT = 'DRAFT', _('Draft')
    PROCESSED = 'PROCESSED', _('Processed / Approved')
    PAID = 'PAID', _('Paid')


class Employee(TenantOwnedModel):
    employee_code = models.CharField(max_length=50, db_index=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(db_index=True)
    phone = models.CharField(max_length=30, blank=True)
    department = models.CharField(max_length=100, default='OPERATIONS')
    designation = models.CharField(max_length=100)
    date_of_joining = models.DateField()
    status = models.CharField(max_length=30, choices=EmployeeStatus.choices, default=EmployeeStatus.ACTIVE, db_index=True)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='employee_profile'
    )

    class Meta:
        unique_together = ('tenant', 'employee_code')
        indexes = [
            models.Index(fields=['tenant', 'status']),
        ]

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.employee_code})"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"


class LeaveRequest(TenantOwnedModel):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='leave_requests')
    leave_type = models.CharField(max_length=50, default='ANNUAL')
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.TextField()
    status = models.CharField(max_length=30, choices=LeaveStatus.choices, default=LeaveStatus.PENDING)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)


class SalaryStructure(TenantOwnedModel):
    employee = models.OneToOneField(Employee, on_delete=models.CASCADE, related_name='salary_structure')
    basic_salary = models.DecimalField(max_digits=12, decimal_places=2)
    allowances = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    deductions = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    net_salary = models.DecimalField(max_digits=12, decimal_places=2)

    def save(self, *args, **kwargs):
        self.net_salary = (self.basic_salary + self.allowances) - self.deductions
        super().save(*args, **kwargs)


class Payroll(TenantOwnedModel):
    payroll_month = models.PositiveSmallIntegerField()  # 1 to 12
    payroll_year = models.PositiveIntegerField()
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='payrolls')
    basic_pay = models.DecimalField(max_digits=12, decimal_places=2)
    allowances = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    deductions = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    net_pay = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=30, choices=PayrollStatus.choices, default=PayrollStatus.DRAFT)
    payment_date = models.DateField(null=True, blank=True)

    class Meta:
        unique_together = ('tenant', 'employee', 'payroll_month', 'payroll_year')
        indexes = [
            models.Index(fields=['tenant', 'payroll_year', 'payroll_month']),
        ]


class EmploymentDocument(TenantOwnedModel):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='documents')
    title = models.CharField(max_length=150)
    document_type = models.CharField(max_length=50)
    file_path = models.CharField(max_length=500)
    uploaded_at = models.DateTimeField(auto_now_add=True)
