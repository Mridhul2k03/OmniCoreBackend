from django.utils import timezone
from apps.notifications.models import Notification, NotificationType, NotificationPriority


class NotificationService:
    @staticmethod
    def send_notification(
        tenant,
        recipient,
        notification_type: str,
        title: str,
        message: str,
        priority: str = NotificationPriority.MEDIUM,
        target_type: str = '',
        target_id: str = '',
        actor=None
    ) -> Notification:
        return Notification.objects.create(
            tenant=tenant,
            recipient=recipient,
            type=notification_type,
            title=title,
            message=message,
            priority=priority,
            target_type=target_type,
            target_id=str(target_id),
            created_by=actor
        )
