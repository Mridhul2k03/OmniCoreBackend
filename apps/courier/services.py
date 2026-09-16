import random
import string
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from apps.courier.models import (
    Shipment, ShipmentStatus, TrackingEvent, Hub, HubShipment,
    SortingRecord, SortingStatus, Delivery, DeliveryStatus, DeliveryAttempt,
    ProofOfDelivery, VerificationMethod, CourierAgent, CourierCommission,
    CourierExpense, CourierPayout, PayoutStatus, ShipmentPickup, PickupStatus
)
from apps.audit.services import AuditService



def generate_awb():
    """Generate tenant-safe authoritative uppercase AWB code e.g. OCT-AWB-AB12CD34"""
    suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    awb = f"OCT-AWB-{suffix}"
    while Shipment.objects.filter(awb_number=awb).exists():
        suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        awb = f"OCT-AWB-{suffix}"
    return awb


def generate_otp():
    """Generate 6-digit server-side numeric OTP"""
    return f"{random.randint(100000, 999999)}"


class ShipmentWorkflowService:
    ALLOWED_TRANSITIONS = {
        ShipmentStatus.BOOKED: [ShipmentStatus.PICKUP_ASSIGNED, ShipmentStatus.CANCELLED, ShipmentStatus.AT_HUB],
        ShipmentStatus.PICKUP_ASSIGNED: [ShipmentStatus.PICKUP_IN_PROGRESS, ShipmentStatus.CANCELLED],
        ShipmentStatus.PICKUP_IN_PROGRESS: [ShipmentStatus.PICKED_UP, ShipmentStatus.PICKUP_ASSIGNED, ShipmentStatus.CANCELLED],
        ShipmentStatus.PICKED_UP: [ShipmentStatus.AT_HUB],
        ShipmentStatus.AT_HUB: [ShipmentStatus.SORTING_PENDING, ShipmentStatus.SORTING, ShipmentStatus.IN_TRANSIT],
        ShipmentStatus.SORTING_PENDING: [ShipmentStatus.SORTING],
        ShipmentStatus.SORTING: [ShipmentStatus.SORTED],
        ShipmentStatus.SORTED: [ShipmentStatus.IN_TRANSIT, ShipmentStatus.DESTINATION_HUB],
        ShipmentStatus.IN_TRANSIT: [ShipmentStatus.DESTINATION_HUB, ShipmentStatus.AT_HUB],
        ShipmentStatus.DESTINATION_HUB: [ShipmentStatus.OUT_FOR_DELIVERY],
        ShipmentStatus.OUT_FOR_DELIVERY: [ShipmentStatus.DELIVERY_ATTEMPTED, ShipmentStatus.DELIVERED, ShipmentStatus.DELIVERY_FAILED, ShipmentStatus.RETURNED],
        ShipmentStatus.DELIVERY_ATTEMPTED: [ShipmentStatus.OUT_FOR_DELIVERY, ShipmentStatus.RETURNED, ShipmentStatus.DELIVERY_FAILED],
        ShipmentStatus.DELIVERY_FAILED: [ShipmentStatus.OUT_FOR_DELIVERY, ShipmentStatus.RETURNED],
        ShipmentStatus.RETURNED: [],
        ShipmentStatus.DELIVERED: [],
        ShipmentStatus.CANCELLED: [],
    }

    @classmethod
    @transaction.atomic
    def transition_status(cls, shipment: Shipment, new_status: str, actor=None, location="", description="", metadata=None):
        if new_status not in dict(ShipmentStatus.choices):
            raise ValidationError(f"Invalid target status: {new_status}")

        allowed = cls.ALLOWED_TRANSITIONS.get(shipment.status, [])
        if new_status not in allowed and shipment.status != new_status:
            raise ValidationError(
                f"Cannot transition shipment {shipment.awb_number} from {shipment.status} to {new_status}. "
                f"Allowed transitions: {allowed}"
            )

        old_status = shipment.status
        shipment.status = new_status
        shipment.save(update_fields=['status', 'updated_at'])

        event_desc = description or f"Shipment status transitioned from {old_status} to {new_status}"
        event = TrackingEvent.objects.create(
            tenant=shipment.tenant,
            shipment=shipment,
            event_type=f"STATUS_{new_status}",
            status=new_status,
            location=location or (shipment.current_hub.name if shipment.current_hub else shipment.sender_city),
            actor=actor,
            description=event_desc,
            metadata=metadata or {}
        )

        AuditService.record(
            action="SHIPMENT_STATUS_UPDATED",
            actor=actor,
            tenant=shipment.tenant,
            target_type="Shipment",
            target_id=str(shipment.id),
            before_snapshot={"status": old_status},
            after_snapshot={"status": new_status}
        )
        return event

    @classmethod
    @transaction.atomic
    def record_pickup_progress(cls, pickup: ShipmentPickup, action: str, actor=None, reason="", notes=""):
        shipment = pickup.shipment
        if action == "ASSIGN":
            pickup.status = PickupStatus.ASSIGNED
            pickup.notes = notes
            pickup.save(update_fields=['status', 'notes', 'updated_at'])
            cls.transition_status(shipment, ShipmentStatus.PICKUP_ASSIGNED, actor=actor, description=f"Pickup leg #{pickup.sequence} assigned")
        elif action == "START":
            pickup.status = PickupStatus.IN_PROGRESS
            pickup.notes = notes
            pickup.save(update_fields=['status', 'notes', 'updated_at'])
            cls.transition_status(shipment, ShipmentStatus.PICKUP_IN_PROGRESS, actor=actor, description=f"Pickup leg #{pickup.sequence} in progress")
        elif action == "COMPLETE":
            pickup.status = PickupStatus.COMPLETED
            pickup.actual_pickup_time = timezone.now()
            pickup.notes = notes
            pickup.save(update_fields=['status', 'actual_pickup_time', 'notes', 'updated_at'])
            cls.transition_status(shipment, ShipmentStatus.PICKED_UP, actor=actor, description=f"Pickup leg #{pickup.sequence} completed")
        elif action == "FAIL":
            pickup.status = PickupStatus.FAILED
            pickup.failure_reason = reason
            pickup.notes = notes
            pickup.save(update_fields=['status', 'failure_reason', 'notes', 'updated_at'])
            TrackingEvent.objects.create(
                tenant=shipment.tenant,
                shipment=shipment,
                event_type="PICKUP_FAILED",
                status=shipment.status,
                location=pickup.address,
                actor=actor,
                description=f"Pickup leg #{pickup.sequence} failed: {reason}",
                metadata={"reason": reason}
            )
        elif action == "RESCHEDULE":
            pickup.status = PickupStatus.RESCHEDULED
            pickup.notes = notes
            pickup.save(update_fields=['status', 'notes', 'updated_at'])
        else:
            raise ValidationError(f"Unknown pickup action: {action}")
        return pickup


class HubSortingService:
    @classmethod
    @transaction.atomic
    def process_sorting(cls, shipment: Shipment, source_hub: Hub, destination_hub: Hub, operator=None, sorting_category="STANDARD", notes=""):
        if shipment.tenant_id != source_hub.tenant_id:
            raise ValidationError("Hub tenant mismatch with shipment.")
        if destination_hub and shipment.tenant_id != destination_hub.tenant_id:
            raise ValidationError("Destination hub tenant mismatch.")

        # Update Hub Movement
        HubShipment.objects.create(
            tenant=shipment.tenant,
            hub=source_hub,
            shipment=shipment,
            status="SORTED"
        )

        record = SortingRecord.objects.create(
            tenant=shipment.tenant,
            shipment=shipment,
            source_hub=source_hub,
            destination_hub=destination_hub,
            sorting_category=sorting_category,
            operator=operator,
            status=SortingStatus.SORTED,
            notes=notes
        )

        shipment.current_hub = source_hub
        if destination_hub:
            shipment.destination_hub = destination_hub
        shipment.status = ShipmentStatus.SORTED
        shipment.save(update_fields=['current_hub', 'destination_hub', 'status', 'updated_at'])

        TrackingEvent.objects.create(
            tenant=shipment.tenant,
            shipment=shipment,
            event_type="SORTING_COMPLETED",
            status=ShipmentStatus.SORTED,
            location=f"{source_hub.name} ({source_hub.code})",
            actor=operator,
            description=f"Shipment sorted at {source_hub.name} for destination {destination_hub.name if destination_hub else 'Direct'}",
            metadata={"category": sorting_category, "source_hub": source_hub.code}
        )

        AuditService.record(
            action="SHIPMENT_SORTED",
            actor=operator,
            tenant=shipment.tenant,
            target_type="SortingRecord",
            target_id=str(record.id),
            metadata={"source_hub": source_hub.code, "status": SortingStatus.SORTED}
        )
        return record


class ProofOfDeliveryService:
    @classmethod
    @transaction.atomic
    def generate_otp_for_delivery(cls, delivery: Delivery):
        otp = generate_otp()
        pod, created = ProofOfDelivery.objects.get_or_create(
            delivery=delivery,
            defaults={
                'tenant': delivery.tenant,
                'verification_method': VerificationMethod.OTP,
                'otp_code': otp,
                'recipient_name': delivery.recipient_name,
            }
        )
        if not created:
            pod.otp_code = otp
            pod.otp_verified = False
            pod.save(update_fields=['otp_code', 'otp_verified', 'updated_at'])
        return otp

    @classmethod
    @transaction.atomic
    def verify_and_complete_pod(cls, delivery: Delivery, entered_otp=None, signature_file="", recipient_name="", agent=None, notes=""):
        pod, _ = ProofOfDelivery.objects.get_or_create(
            delivery=delivery,
            defaults={'tenant': delivery.tenant, 'recipient_name': delivery.recipient_name}
        )

        if pod.verification_method in [VerificationMethod.OTP, VerificationMethod.BOTH]:
            if not entered_otp or entered_otp != pod.otp_code:
                raise ValidationError("Invalid or missing Proof of Delivery OTP code.")
            pod.otp_verified = True

        if signature_file:
            pod.digital_signature_file = signature_file
        if recipient_name:
            pod.recipient_name = recipient_name
        
        pod.delivery_timestamp = timezone.now()
        pod.agent = agent or delivery.agent
        pod.notes = notes
        pod.save()

        # Update delivery and shipment status
        delivery.delivery_status = DeliveryStatus.DELIVERED
        delivery.save(update_fields=['delivery_status', 'updated_at'])

        shipment = delivery.shipment
        shipment.status = ShipmentStatus.DELIVERED
        shipment.save(update_fields=['status', 'updated_at'])

        # Record Tracking Event
        TrackingEvent.objects.create(
            tenant=shipment.tenant,
            shipment=shipment,
            event_type="DELIVERED",
            status=ShipmentStatus.DELIVERED,
            location=delivery.delivery_address,
            actor=agent.user if agent and agent.user else None,
            description=f"Delivered successfully to {pod.recipient_name}. Verified via {pod.verification_method}.",
            metadata={"verification_method": pod.verification_method}
        )

        # Accrue Agent Commission if assigned
        if delivery.agent:
            commission_amt = delivery.agent.commission_rate_per_delivery
            if commission_amt > 0:
                CourierCommission.objects.create(
                    tenant=delivery.tenant,
                    agent=delivery.agent,
                    delivery=delivery,
                    shipment=shipment,
                    commission_amount=commission_amt,
                    status="EARNED"
                )

        AuditService.record(
            action="POD_VERIFIED_DELIVERED",
            actor=agent.user if agent and agent.user else None,
            tenant=delivery.tenant,
            target_type="ProofOfDelivery",
            target_id=str(pod.id),
            metadata={"status": "DELIVERED", "recipient": pod.recipient_name}
        )
        return pod


class CourierPayoutService:
    @classmethod
    @transaction.atomic
    def process_agent_payout(cls, agent: CourierAgent, period_start, period_end, idempotency_key=None, actor=None):
        tenant = agent.tenant
        if idempotency_key:
            existing = CourierPayout.objects.filter(tenant=tenant, idempotency_key=idempotency_key).first()
            if existing:
                return existing

        commissions = CourierCommission.objects.filter(
            tenant=tenant,
            agent=agent,
            status="EARNED",
            date__range=[period_start, period_end]
        )
        gross = sum([c.commission_amount for c in commissions])

        expenses = CourierExpense.objects.filter(
            tenant=tenant,
            agent=agent,
            is_approved=True,
            date__range=[period_start, period_end]
        )
        deductions = sum([e.amount for e in expenses])
        net = gross - deductions

        payout_suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        payout_number = f"PAY-{timezone.now().strftime('%Y%m')}-{payout_suffix}"

        payout = CourierPayout.objects.create(
            tenant=tenant,
            payout_number=payout_number,
            agent=agent,
            gross_amount=gross,
            total_deductions=deductions,
            net_payable=net,
            period_start=period_start,
            period_end=period_end,
            status=PayoutStatus.APPROVED,
            idempotency_key=idempotency_key,
            paid_at=timezone.now()
        )

        # Mark commissions settled
        commissions.update(status="SETTLED")

        AuditService.record(
            action="COURIER_PAYOUT_APPROVED",
            actor=actor,
            tenant=tenant,
            target_type="CourierPayout",
            target_id=str(payout.id),
            metadata={"net_payable": str(net), "status": PayoutStatus.APPROVED}
        )
        return payout
