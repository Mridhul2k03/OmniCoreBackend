from rest_framework import serializers
from apps.audit.models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    actor_email = serializers.CharField(source='actor.email', read_only=True)

    class Meta:
        model = AuditLog
        fields = [
            'id', 'actor', 'actor_email', 'tenant', 'action', 'target_type',
            'target_id', 'ip_address', 'user_agent', 'before_snapshot',
            'after_snapshot', 'metadata', 'timestamp'
        ]
        read_only_fields = fields
