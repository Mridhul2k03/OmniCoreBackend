from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter

from apps.core.viewsets import TenantModelViewSet
from apps.notifications.models import Notification
from apps.notifications.serializers import NotificationSerializer


class NotificationViewSet(TenantModelViewSet):
    serializer_class = NotificationSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['type', 'priority']
    ordering_fields = ['created_at']

    def get_queryset(self):
        # User only views their own notifications in the active tenant
        tenant = getattr(self.request, 'tenant', None)
        if not tenant:
            return Notification.objects.none()
        return Notification.objects.filter(tenant=tenant, recipient=self.request.user)

    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        notification = self.get_object()
        notification.read_at = timezone.now()
        notification.save(update_fields=['read_at'])
        return Response({'message': 'Notification marked as read.'})

    @action(detail=False, methods=['post'])
    def mark_all_read(self, request):
        count = self.get_queryset().filter(read_at__isnull=True).update(read_at=timezone.now())
        return Response({'message': f"{count} notifications marked as read."})
