from django.db import transaction
from apps.crm.models import Customer, Lead, LeadStatus
from apps.audit.services import AuditService
from apps.core.exceptions import BusinessValidationError


class CustomerService:
    @staticmethod
    def convert_lead_to_customer(lead: Lead, credit_limit=0, payment_terms_days=30, actor=None) -> Customer:
        """
        Converts a qualified sales lead into an active Customer.
        """
        if lead.converted_customer:
            raise BusinessValidationError("This lead has already been converted to a customer.")

        with transaction.atomic():
            company_name = lead.company_name or lead.name
            customer = Customer.objects.create(
                tenant=lead.tenant,
                company_name=company_name,
                contact_person=lead.name,
                email=lead.email,
                phone=lead.phone,
                credit_limit=credit_limit,
                payment_terms_days=payment_terms_days,
                is_active=True
            )

            lead.status = LeadStatus.WON
            lead.converted_customer = customer
            lead.save(update_fields=['status', 'converted_customer'])

            AuditService.record(
                action='LEAD_CONVERTED_TO_CUSTOMER',
                actor=actor,
                tenant=lead.tenant,
                target_type='Customer',
                target_id=str(customer.id),
                after_snapshot={'company_name': customer.company_name, 'lead_id': str(lead.id)}
            )

            return customer
