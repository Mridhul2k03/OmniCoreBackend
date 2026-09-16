import logging
from celery import shared_task
from django.db import models
from django.utils import timezone
from apps.fleet.models import VehicleDocument
from apps.drivers.models import Driver
from apps.warehouse.models import SparePart
from apps.finance.models import Invoice, InvoiceStatus
from apps.notifications.services import NotificationService
from apps.notifications.models import NotificationType, NotificationPriority
from apps.tenants.models import TenantUser

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def scan_expiring_vehicle_documents(self):
    """
    Checks for vehicle compliance documents expiring within 15 days
    and alerts tenant administrators.
    """
    try:
        now = timezone.now().date()
        threshold = now + timezone.timedelta(days=15)
        expiring = VehicleDocument.objects.filter(
            expiry_date__lte=threshold,
            expiry_date__gte=now,
            status='VALID'
        ).select_related('vehicle', 'tenant')

        notified_count = 0
        for doc in expiring:
            admins = TenantUser.objects.filter(
                tenant=doc.tenant,
                role__code='TENANT_ADMIN',
                is_active=True
            ).select_related('user')

            for admin in admins:
                NotificationService.send_notification(
                    tenant=doc.tenant,
                    recipient=admin.user,
                    notification_type=NotificationType.VEHICLE_DOCUMENT_EXPIRY,
                    title=f"Vehicle Document Expiring: {doc.vehicle.registration_number}",
                    message=f"The {doc.get_document_type_display()} for {doc.vehicle.registration_number} expires on {doc.expiry_date}.",
                    priority=NotificationPriority.HIGH,
                    target_type='VehicleDocument',
                    target_id=str(doc.id)
                )
                notified_count += 1

        logger.info(f"scan_expiring_vehicle_documents completed. Sent {notified_count} notifications.")
        return {'status': 'success', 'notified': notified_count}
    except Exception as exc:
        logger.error(f"Error in scan_expiring_vehicle_documents: {exc}", exc_info=True)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def scan_expiring_driver_licenses(self):
    """
    Checks for driver licenses expiring within 15 days.
    """
    try:
        now = timezone.now().date()
        threshold = now + timezone.timedelta(days=15)
        expiring_drivers = Driver.objects.filter(
            license_expiry__lte=threshold,
            license_expiry__gte=now,
            status='AVAILABLE'
        ).select_related('tenant')

        count = 0
        for driver in expiring_drivers:
            admins = TenantUser.objects.filter(
                tenant=driver.tenant,
                role__code='TENANT_ADMIN',
                is_active=True
            ).select_related('user')

            for admin in admins:
                NotificationService.send_notification(
                    tenant=driver.tenant,
                    recipient=admin.user,
                    notification_type=NotificationType.DRIVER_LICENSE_EXPIRY,
                    title=f"Driver License Expiring: {driver.full_name}",
                    message=f"Driving license {driver.license_number} for {driver.full_name} will expire on {driver.license_expiry}.",
                    priority=NotificationPriority.HIGH,
                    target_type='Driver',
                    target_id=str(driver.id)
                )
                count += 1

        return {'status': 'success', 'notified': count}
    except Exception as exc:
        logger.error(f"Error in scan_expiring_driver_licenses: {exc}", exc_info=True)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def scan_low_inventory(self):
    """
    Identifies inventory spare parts that have breached their reorder thresholds.
    """
    try:
        parts = SparePart.objects.filter(
            current_stock__lte=models.F('reorder_level')
        ).select_related('tenant')

        count = 0
        for part in parts:
            warehouse_users = TenantUser.objects.filter(
                tenant=part.tenant,
                is_active=True
            ).select_related('user')

            for tu in warehouse_users:
                NotificationService.send_notification(
                    tenant=part.tenant,
                    recipient=tu.user,
                    notification_type=NotificationType.LOW_INVENTORY,
                    title=f"Low Stock Alert: {part.name}",
                    message=f"Stock for '{part.name}' ({part.part_number}) is at {part.current_stock}, below reorder level {part.reorder_level}.",
                    priority=NotificationPriority.MEDIUM,
                    target_type='SparePart',
                    target_id=str(part.id)
                )
                count += 1

        return {'status': 'success', 'notified': count}
    except Exception as exc:
        logger.error(f"Error in scan_low_inventory: {exc}", exc_info=True)
        raise self.retry(exc=exc)
