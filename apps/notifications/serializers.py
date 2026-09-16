from rest_framework import serializers
from apps.notifications.models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    is_read = serializers.BooleanField(read_only=True)

    class Meta:
        model = Notification
        fields = [
            'id', 'type', 'title', 'message', 'priority', 'read_at',
            'is_read', 'target_type', 'target_id', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']
