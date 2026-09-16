from decimal import Decimal
from django.db import transaction
from apps.warehouse.models import SparePart, Warehouse, InventoryTransaction, TransactionType
from apps.core.exceptions import BusinessValidationError
from apps.audit.services import AuditService


class InventoryService:
    """
    Guarantees ACID compliance, row locking, and immutable ledgering
    for all inventory movements.
    """
    @classmethod
    def record_stock_movement(
        cls,
        tenant,
        spare_part_id,
        warehouse_id,
        transaction_type: str,
        quantity: Decimal,
        reference_id: str = '',
        reference_type: str = '',
        notes: str = '',
        actor=None
    ) -> InventoryTransaction:
        if transaction_type not in TransactionType.values:
            raise BusinessValidationError(f"Invalid transaction type '{transaction_type}'.")

        qty = Decimal(str(quantity))
        if qty == 0:
            raise BusinessValidationError("Quantity must be non-zero.")

        # Ensure deductions are signed negative and additions positive
        if transaction_type in [TransactionType.ISSUE] and qty > 0:
            qty = -qty
        elif transaction_type in [TransactionType.RECEIVE, TransactionType.RETURN] and qty < 0:
            qty = abs(qty)

        with transaction.atomic():
            part = SparePart.objects.select_for_update().filter(id=spare_part_id, tenant=tenant).first()
            if not part:
                raise BusinessValidationError("Spare part not found in tenant scope.")

            warehouse = Warehouse.objects.filter(id=warehouse_id, tenant=tenant).first()
            if not warehouse:
                raise BusinessValidationError("Warehouse not found in tenant scope.")

            previous_stock = part.current_stock
            new_stock = previous_stock + qty

            if new_stock < 0:
                raise BusinessValidationError(
                    f"Insufficient stock for '{part.name}'. Available: {previous_stock}, requested: {abs(qty)}.",
                    code='INSUFFICIENT_STOCK'
                )

            # Record immutable transaction
            tx = InventoryTransaction.objects.create(
                tenant=tenant,
                spare_part=part,
                warehouse=warehouse,
                transaction_type=transaction_type,
                quantity=qty,
                previous_stock=previous_stock,
                new_stock=new_stock,
                reference_id=reference_id,
                reference_type=reference_type,
                notes=notes,
                created_by=actor
            )

            # Update cached stock
            part.current_stock = new_stock
            part.save(update_fields=['current_stock'])

            AuditService.record(
                action='INVENTORY_TRANSACTION_RECORDED',
                actor=actor,
                tenant=tenant,
                target_type='SparePart',
                target_id=str(part.id),
                before_snapshot={'stock': str(previous_stock)},
                after_snapshot={'stock': str(new_stock), 'tx_id': str(tx.id)},
                metadata={'tx_type': transaction_type, 'delta': str(qty)}
            )

            return tx


class CrossDockService:
    @classmethod
    @transaction.atomic
    def start_cross_dock(cls, tenant, warehouse, source_loc, dest_loc, inbound_carrier="", operator=None, notes=""):
        import random, string
        suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        cd_num = f"XD-{warehouse.code}-{suffix}"

        from apps.warehouse.models import CrossDockOperation, CrossDockStatus
        cd = CrossDockOperation.objects.create(
            tenant=tenant,
            cross_dock_number=cd_num,
            warehouse=warehouse,
            source_location=source_loc,
            destination_location=dest_loc,
            inbound_carrier=inbound_carrier,
            operator=operator,
            status=CrossDockStatus.INBOUND_RECEIVED,
            notes=notes
        )
        return cd

    @classmethod
    @transaction.atomic
    def advance_status(cls, cross_dock, new_status, outbound_carrier="", actor=None, notes=""):
        from django.utils import timezone
        from apps.warehouse.models import CrossDockStatus
        from apps.courier.models import TrackingEvent, ShipmentStatus

        cross_dock.status = new_status
        if outbound_carrier:
            cross_dock.outbound_carrier = outbound_carrier
        if new_status in [CrossDockStatus.OUTBOUND_DISPATCHED, CrossDockStatus.COMPLETED]:
            cross_dock.outbound_time = timezone.now()
        if notes:
            cross_dock.notes = f"{cross_dock.notes}\n{notes}".strip()
        cross_dock.save()

        # Update linked shipments tracking event
        for item in cross_dock.shipments.select_related('shipment').all():
            if item.shipment:
                TrackingEvent.objects.create(
                    tenant=cross_dock.tenant,
                    shipment=item.shipment,
                    event_type=f"CROSS_DOCK_{new_status}",
                    status=item.shipment.status,
                    location=cross_dock.warehouse.name,
                    actor=actor,
                    description=f"Cross-dock {cross_dock.cross_dock_number} updated to {new_status}",
                    metadata={"cross_dock": cross_dock.cross_dock_number, "status": new_status}
                )

        return cross_dock


class ShipmentConsolidationService:
    @classmethod
    @transaction.atomic
    def create_group(cls, tenant, warehouse, destination_zone, date_from, date_to, hub=None, notes=""):
        import random, string
        suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        group_code = f"GRP-{destination_zone[:3].upper()}-{suffix}"

        from apps.warehouse.models import ConsolidationGroup, ConsolidationStatus
        group = ConsolidationGroup.objects.create(
            tenant=tenant,
            group_code=group_code,
            warehouse=warehouse,
            hub=hub,
            destination_zone=destination_zone,
            date_from=date_from,
            date_to=date_to,
            status=ConsolidationStatus.OPEN,
            notes=notes
        )
        return group

    @classmethod
    @transaction.atomic
    def add_item(cls, group, shipment=None, invoice_ref="", parcels=1, weight_kg=0.0):
        from apps.warehouse.models import ConsolidatedShipmentItem, ConsolidationStatus
        from apps.courier.models import TrackingEvent

        if group.status != ConsolidationStatus.OPEN:
            raise BusinessValidationError("Cannot add items to a closed or dispatched consolidation group.")

        item = ConsolidatedShipmentItem.objects.create(
            tenant=group.tenant,
            group=group,
            shipment=shipment,
            invoice_reference=invoice_ref or (shipment.invoice.invoice_number if shipment and shipment.invoice else ""),
            parcel_count=parcels,
            weight_kg=weight_kg
        )

        group.total_parcels += parcels
        group.total_weight_kg = Decimal(str(group.total_weight_kg)) + Decimal(str(weight_kg))
        group.save(update_fields=['total_parcels', 'total_weight_kg', 'updated_at'])


        if shipment:
            TrackingEvent.objects.create(
                tenant=group.tenant,
                shipment=shipment,
                event_type="CONSOLIDATED",
                status=shipment.status,
                location=group.warehouse.name,
                description=f"Added to consolidation container {group.group_code} for {group.destination_zone}",
                metadata={"group_code": group.group_code}
            )

        return item

