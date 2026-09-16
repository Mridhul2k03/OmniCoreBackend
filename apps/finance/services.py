from decimal import Decimal
import uuid
from django.db import transaction
from django.utils import timezone
from apps.finance.models import Invoice, Payment, InvoiceStatus
from apps.core.exceptions import BusinessValidationError
from apps.audit.services import AuditService


class FinanceService:
    @classmethod
    def record_payment(
        cls,
        invoice: Invoice,
        amount: Decimal,
        payment_method: str = 'BANK_TRANSFER',
        reference_number: str = '',
        idempotency_key: str = None,
        notes: str = '',
        actor=None
    ) -> Payment:
        """
        Records payment allocation with strict idempotency and invoice balance synchronization.
        """
        amount = Decimal(str(amount))
        if amount <= 0:
            raise BusinessValidationError("Payment amount must be greater than zero.")

        tenant = invoice.tenant

        # Check idempotency
        if idempotency_key:
            existing = Payment.objects.filter(tenant=tenant, idempotency_key=idempotency_key).first()
            if existing:
                return existing

        with transaction.atomic():
            # Lock invoice row
            inv = Invoice.objects.select_for_update().get(id=invoice.id)
            if inv.status in [InvoiceStatus.CANCELLED]:
                raise BusinessValidationError("Cannot record payments on a cancelled invoice.")

            payment_number = f"PAY-{uuid.uuid4().hex[:8].upper()}"

            payment = Payment.objects.create(
                tenant=tenant,
                invoice=inv,
                payment_number=payment_number,
                amount=amount,
                payment_date=timezone.now().date(),
                payment_method=payment_method,
                reference_number=reference_number,
                idempotency_key=idempotency_key,
                notes=notes,
                created_by=actor
            )

            inv.paid_amount += amount
            inv.update_balance()

            AuditService.record(
                action='PAYMENT_RECORDED',
                actor=actor,
                tenant=tenant,
                target_type='Payment',
                target_id=str(payment.id),
                after_snapshot={
                    'payment_number': payment.payment_number,
                    'amount': str(amount),
                    'invoice_balance': str(inv.balance_due)
                }
            )

            return payment
