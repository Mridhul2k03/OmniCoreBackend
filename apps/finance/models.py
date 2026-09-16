import uuid
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from apps.core.models import TenantOwnedModel


class InvoiceStatus(models.TextChoices):
    DRAFT = 'DRAFT', _('Draft')
    ISSUED = 'ISSUED', _('Issued')
    PARTIALLY_PAID = 'PARTIALLY_PAID', _('Partially Paid')
    PAID = 'PAID', _('Paid in Full')
    OVERDUE = 'OVERDUE', _('Overdue')
    CANCELLED = 'CANCELLED', _('Cancelled')


class PaymentMethod(models.TextChoices):
    BANK_TRANSFER = 'BANK_TRANSFER', _('NEFT / RTGS / Wire Transfer')
    CREDIT_CARD = 'CREDIT_CARD', _('Corporate Credit Card')
    CHEQUE = 'CHEQUE', _('Cheque / Demand Draft')
    CASH = 'CASH', _('Cash')
    UPI = 'UPI', _('UPI / Instant Payment')


class ExpenseCategory(models.TextChoices):
    FUEL = 'FUEL', _('Fuel & Lubricants')
    TOLL = 'TOLL', _('Highway Tolls')
    MAINTENANCE = 'MAINTENANCE', _('Fleet Maintenance & Repairs')
    SALARY = 'SALARY', _('Driver & Staff Payroll')
    RENT = 'RENT', _('Warehouse & Office Lease')
    INSURANCE = 'INSURANCE', _('Insurance Premium')
    OFFICE = 'OFFICE', _('Office & Administrative')
    OTHER = 'OTHER', _('Other General Operating Expense')


class Invoice(TenantOwnedModel):
    """
    Commercial sales invoice billed to a freight client or contract partner.
    """
    invoice_number = models.CharField(max_length=100, db_index=True)
    customer = models.ForeignKey('crm.Customer', on_delete=models.CASCADE, related_name='invoices')
    trip = models.ForeignKey('trips.Trip', null=True, blank=True, on_delete=models.SET_NULL, related_name='invoices')
    contract = models.ForeignKey('contracts.Contract', null=True, blank=True, on_delete=models.SET_NULL, related_name='invoices')
    issue_date = models.DateField(db_index=True)
    due_date = models.DateField(db_index=True)
    subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=0.00)
    tax_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0.00)
    total_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0.00)
    paid_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0.00)
    balance_due = models.DecimalField(max_digits=14, decimal_places=2, default=0.00)
    status = models.CharField(
        max_length=30,
        choices=InvoiceStatus.choices,
        default=InvoiceStatus.DRAFT,
        db_index=True
    )
    notes = models.TextField(blank=True)

    class Meta:
        unique_together = ('tenant', 'invoice_number')
        indexes = [
            models.Index(fields=['tenant', 'status']),
            models.Index(fields=['tenant', 'due_date']),
            models.Index(fields=['tenant', 'customer']),
        ]

    def __str__(self):
        return f"INV {self.invoice_number} - {self.customer.company_name} (${self.total_amount})"

    def update_balance(self):
        self.balance_due = max(0, self.total_amount - self.paid_amount)
        if self.paid_amount >= self.total_amount and self.total_amount > 0:
            self.status = InvoiceStatus.PAID
        elif self.paid_amount > 0:
            self.status = InvoiceStatus.PARTIALLY_PAID
        self.save(update_fields=['paid_amount', 'balance_due', 'status'])


class InvoiceItem(TenantOwnedModel):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='items')
    description = models.CharField(max_length=255)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1.00)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    total_amount = models.DecimalField(max_digits=14, decimal_places=2)

    def save(self, *args, **kwargs):
        self.total_amount = self.quantity * self.unit_price
        super().save(*args, **kwargs)


class Payment(TenantOwnedModel):
    """
    Receipt of funds against an issued invoice.
    Protected with idempotency mechanisms.
    """
    payment_number = models.CharField(max_length=100, db_index=True)
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    payment_date = models.DateField(db_index=True)
    payment_method = models.CharField(max_length=30, choices=PaymentMethod.choices, default=PaymentMethod.BANK_TRANSFER)
    reference_number = models.CharField(max_length=100, blank=True)
    idempotency_key = models.CharField(max_length=128, blank=True, null=True, db_index=True)
    notes = models.TextField(blank=True)

    class Meta:
        unique_together = ('tenant', 'idempotency_key')
        indexes = [
            models.Index(fields=['tenant', 'payment_date']),
        ]

    def __str__(self):
        return f"Payment {self.payment_number} (${self.amount}) for INV {self.invoice.invoice_number}"


class Expense(TenantOwnedModel):
    expense_number = models.CharField(max_length=100, db_index=True)
    category = models.CharField(max_length=30, choices=ExpenseCategory.choices, db_index=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    expense_date = models.DateField(db_index=True)
    description = models.TextField()
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        indexes = [
            models.Index(fields=['tenant', 'expense_date']),
            models.Index(fields=['tenant', 'category']),
        ]


class FuelTransaction(TenantOwnedModel):
    vehicle = models.ForeignKey('fleet.Vehicle', on_delete=models.CASCADE, related_name='fuel_transactions')
    driver = models.ForeignKey('drivers.Driver', null=True, blank=True, on_delete=models.SET_NULL, related_name='fuel_purchases')
    transaction_date = models.DateTimeField(db_index=True)
    fuel_station = models.CharField(max_length=200)
    fuel_liters = models.DecimalField(max_digits=10, decimal_places=2)
    rate_per_liter = models.DecimalField(max_digits=8, decimal_places=2)
    total_cost = models.DecimalField(max_digits=12, decimal_places=2)
    odometer_reading = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)


class TollTransaction(TenantOwnedModel):
    vehicle = models.ForeignKey('fleet.Vehicle', on_delete=models.CASCADE, related_name='toll_transactions')
    toll_plaza = models.CharField(max_length=200)
    tag_id = models.CharField(max_length=100, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    transaction_time = models.DateTimeField(db_index=True)


class Collection(TenantOwnedModel):
    customer = models.ForeignKey('crm.Customer', on_delete=models.CASCADE, related_name='collections')
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    collection_date = models.DateField(db_index=True)
    payment_mode = models.CharField(max_length=50, default='CHEQUE')
    reference_id = models.CharField(max_length=100, blank=True)
