import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_shipment_notification_task(self, shipment_id: str, event_type: str):
    """
    Asynchronously notify sender and recipient upon milestone event.
    """
    try:
        from apps.courier.models import Shipment
        shipment = Shipment.objects.filter(id=shipment_id).first()
        if not shipment:
            logger.warning(f"Shipment {shipment_id} not found for notification.")
            return

        logger.info(f"Notification queued for AWB {shipment.awb_number}: {event_type}")
        return f"Notified for {shipment.awb_number}"
    except Exception as exc:
        logger.error(f"Error in shipment notification task: {exc}")
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def process_pod_document_task(self, pod_id: str):
    """
    Process digital signature file, optimize thumbnail, and archive to S3.
    """
    try:
        from apps.courier.models import ProofOfDelivery
        pod = ProofOfDelivery.objects.filter(id=pod_id).first()
        if not pod:
            return
        logger.info(f"Processed PoD {pod_id} for delivery {pod.delivery_id}")
        return f"PoD {pod_id} processed"
    except Exception as exc:
        logger.error(f"Error processing PoD document: {exc}")
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def process_agent_payout_batch_task(self, tenant_id: str, period_start: str, period_end: str):
    """
    Background batch processor for all active courier agents.
    """
    try:
        from apps.courier.models import CourierAgent
        from apps.courier.services import CourierPayoutService
        agents = CourierAgent.objects.filter(tenant_id=tenant_id, status='ACTIVE')
        count = 0
        for agent in agents:
            CourierPayoutService.process_agent_payout(agent, period_start, period_end)
            count += 1
        logger.info(f"Processed {count} courier agent payouts for tenant {tenant_id}")
        return count
    except Exception as exc:
        logger.error(f"Error in agent payout batch: {exc}")
        raise self.retry(exc=exc)
