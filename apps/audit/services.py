from apps.audit.models import AuditLog


class AuditService:
    """
    Centralized service for emitting immutable audit log events.
    """
    @staticmethod
    def record(
        action: str,
        actor=None,
        tenant=None,
        target_type: str = '',
        target_id: str = '',
        before_snapshot: dict = None,
        after_snapshot: dict = None,
        metadata: dict = None,
        request=None
    ) -> AuditLog:
        ip_address = None
        user_agent = ''

        if request:
            if not actor and hasattr(request, 'user') and request.user.is_authenticated:
                actor = request.user
            if not tenant and hasattr(request, 'tenant') and request.tenant:
                tenant = request.tenant
            
            ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', ''))
            if ',' in ip:
                ip = ip.split(',')[0].strip()
            ip_address = ip if ip else None
            user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]

        return AuditLog.objects.create(
            actor=actor,
            tenant=tenant,
            action=action,
            target_type=target_type,
            target_id=str(target_id),
            ip_address=ip_address,
            user_agent=user_agent,
            before_snapshot=before_snapshot or {},
            after_snapshot=after_snapshot or {},
            metadata=metadata or {},
        )
