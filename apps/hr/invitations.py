import hashlib
import logging
import secrets
from datetime import timedelta
from urllib.parse import quote

from django.conf import settings
from django.contrib.auth import get_user_model, password_validation
from django.core.mail import send_mail
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.audit.services import AuditService
from apps.core.exceptions import BusinessValidationError, PermissionDeniedError
from apps.hr.models import Employee, EmployeeInvitation
from apps.tenants.models import Role, TenantUser

logger = logging.getLogger(__name__)
INVITATION_TTL = timedelta(days=3)
User = get_user_model()


def _token_digest(token):
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def _invitation_url(token):
    return f"{settings.FRONTEND_BASE_URL}/auth/accept-invitation?token={quote(token)}"


def _deliver_invitation(invitation, token):
    employee = invitation.employee
    link = _invitation_url(token)
    subject = f"You are invited to join {invitation.tenant.company_name} on OmniCore"
    body = (
        f"Hello {employee.first_name},\n\n"
        f"{invitation.invited_by.get_full_name() or invitation.invited_by.email} invited you to join "
        f"{invitation.tenant.company_name} as {invitation.role.name}.\n\n"
        f"Use this secure link to activate your account: {link}\n"
        f"This link expires in 3 days and can only be used once.\n\n"
        "If you already have an OmniCore account, accept the invitation and sign in with your existing password."
    )
    try:
        delivered = send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [employee.email], fail_silently=False)
        if delivered != 1:
            raise RuntimeError('Email backend did not accept the invitation email.')
    except Exception as exc:
        logger.exception('Could not deliver employee invitation email for employee %s', employee.id)
        raise BusinessValidationError(
            'Invitation email could not be sent. Check the email service configuration and try again.',
            code='INVITATION_EMAIL_FAILED',
            status_code=503,
        ) from exc
    return link


@transaction.atomic
def create_employee_invitation(*, tenant, invited_by, data):
    tenant = type(tenant).objects.select_for_update().get(pk=tenant.pk)
    email = data['email'].strip().lower()
    employee = Employee.objects.filter(tenant=tenant, email__iexact=email).first()
    if employee and employee.user_id:
        raise BusinessValidationError('An employee with this email already has a linked account.', code='EMPLOYEE_EMAIL_EXISTS')

    existing_user = User.objects.filter(email__iexact=email).first()
    if existing_user and not existing_user.is_active:
        raise BusinessValidationError('This email belongs to a disabled OmniCore account. Contact support before inviting it.')
    if existing_user:
        existing_membership = TenantUser.objects.filter(tenant=tenant, user=existing_user).first()
        if existing_membership and existing_membership.is_primary:
            raise BusinessValidationError('The primary administrator account cannot be invited as an employee.')
        if existing_membership and existing_membership.is_active:
            raise BusinessValidationError('This person already has active access to this organization.')

    if data['role'].code == 'TENANT_ADMIN':
        raise BusinessValidationError('The primary administrator role cannot be assigned through employee invitations.')

    employee_code = employee.employee_code if employee else None
    if not employee_code:
        for _ in range(5):
            candidate = f"EMP-{secrets.token_hex(3).upper()}"
            if not Employee.objects.filter(tenant=tenant, employee_code=candidate).exists():
                employee_code = candidate
                break
        if not employee_code:
            raise BusinessValidationError('Could not allocate an employee code. Please try again.')

    employee_fields = {
        'first_name': data['first_name'].strip(),
        'last_name': data['last_name'].strip(),
        'email': email,
        'phone': data.get('phone', '').strip(),
        'department': data.get('department', 'OPERATIONS').strip().upper(),
        'designation': data['designation'].strip(),
        'date_of_joining': data['date_of_joining'],
    }
    if employee:
        invitation = EmployeeInvitation.objects.select_for_update().filter(employee=employee).first()
        if invitation:
            if invitation.status == EmployeeInvitation.Status.ACCEPTED:
                raise BusinessValidationError('This employee account has already been activated.')
            for field, value in employee_fields.items():
                setattr(employee, field, value)
            employee.save(update_fields=[*employee_fields.keys(), 'updated_at'])
            invitation.role = data['role']
            invitation.save(update_fields=['role', 'updated_at'])
            return resend_employee_invitation(employee=employee, invited_by=invited_by)
        for field, value in employee_fields.items():
            setattr(employee, field, value)
        employee.save(update_fields=[*employee_fields.keys(), 'updated_at'])
    else:
        employee = Employee.objects.create(
            tenant=tenant,
            created_by=invited_by,
            employee_code=employee_code,
            **employee_fields,
        )
    token = secrets.token_urlsafe(36)
    invitation = EmployeeInvitation.objects.create(
        tenant=tenant,
        created_by=invited_by,
        employee=employee,
        role=data['role'],
        invited_by=invited_by,
        token_hash=_token_digest(token),
        expires_at=timezone.now() + INVITATION_TTL,
    )
    link = _deliver_invitation(invitation, token)
    AuditService.record(
        action='EMPLOYEE_INVITED',
        actor=invited_by,
        tenant=tenant,
        target_type='Employee',
        target_id=str(employee.id),
        after_snapshot={'email': email, 'role': data['role'].code, 'employee_code': employee_code},
    )

    result = {'employee': employee, 'invitation': invitation}
    if settings.DEBUG and 'console.EmailBackend' in settings.EMAIL_BACKEND:
        # Only local development returns the one-time link to the authenticated
        # admin, since the console backend cannot deliver email to the invitee.
        result['invitation_url'] = link
    return result


@transaction.atomic
def resend_employee_invitation(*, employee, invited_by):
    if employee.user_id:
        raise BusinessValidationError('This employee has already activated their account.')
    invitation = EmployeeInvitation.objects.select_for_update().filter(employee=employee).select_related('role').first()
    if not invitation or invitation.status == EmployeeInvitation.Status.ACCEPTED:
        raise BusinessValidationError('There is no pending invitation for this employee.')
    token = secrets.token_urlsafe(36)
    invitation.token_hash = _token_digest(token)
    invitation.status = EmployeeInvitation.Status.PENDING
    invitation.expires_at = timezone.now() + INVITATION_TTL
    invitation.invited_by = invited_by
    invitation.save(update_fields=['token_hash', 'status', 'expires_at', 'invited_by', 'updated_at'])
    link = _deliver_invitation(invitation, token)
    AuditService.record(
        action='EMPLOYEE_INVITATION_RESENT',
        actor=invited_by,
        tenant=employee.tenant,
        target_type='Employee',
        target_id=str(employee.id),
        after_snapshot={'email': employee.email, 'role': invitation.role.code},
    )
    result = {'employee': employee, 'invitation': invitation}
    if settings.DEBUG and 'console.EmailBackend' in settings.EMAIL_BACKEND:
        result['invitation_url'] = link
    return result


def get_invitation(token, *, lock=False):
    if not isinstance(token, str) or not token or len(token) > 256:
        raise BusinessValidationError('This invitation link is invalid or has expired.', code='INVITATION_INVALID')
    query = EmployeeInvitation.objects.select_related('employee', 'tenant', 'role')
    if lock:
        query = query.select_for_update()
    invitation = query.filter(token_hash=_token_digest(token), status=EmployeeInvitation.Status.PENDING).first()
    if not invitation:
        raise BusinessValidationError('This invitation link is invalid, expired, or already used.', code='INVITATION_INVALID')
    if invitation.expires_at <= timezone.now():
        invitation.status = EmployeeInvitation.Status.EXPIRED
        invitation.save(update_fields=['status', 'updated_at'])
        raise BusinessValidationError('This invitation link has expired. Ask your organization admin to send a new invitation.', code='INVITATION_EXPIRED')
    return invitation


@transaction.atomic
def accept_employee_invitation(*, token, new_password=None):
    invitation = get_invitation(token, lock=True)
    employee = invitation.employee
    user = User.objects.filter(email__iexact=employee.email).first()
    requires_password = not user or not user.has_usable_password()

    if user and not user.is_active:
        raise BusinessValidationError('This OmniCore account is disabled. Contact support to restore access.')
    if requires_password:
        if not new_password:
            raise BusinessValidationError('Choose a password to activate your account.', fields={'new_password': ['This field is required.']})
        candidate_user = user or User(email=employee.email, first_name=employee.first_name, last_name=employee.last_name)
        try:
            password_validation.validate_password(new_password, candidate_user)
        except ValidationError as exc:
            messages = list(exc.messages)
            raise BusinessValidationError('Choose a stronger password.', fields={'new_password': messages}) from exc
    elif new_password:
        raise BusinessValidationError('This email already has an OmniCore account. Sign in with its existing password after accepting.')

    if not user:
        user = User.objects.create_user(
            email=employee.email,
            password=new_password,
            first_name=employee.first_name,
            last_name=employee.last_name,
            phone=employee.phone,
            is_active=True,
        )
    elif requires_password:
        user.set_password(new_password)
        if not user.first_name:
            user.first_name = employee.first_name
        if not user.last_name:
            user.last_name = employee.last_name
        if not user.phone and employee.phone:
            user.phone = employee.phone
        user.save(update_fields=['password', 'first_name', 'last_name', 'phone'])

    membership = TenantUser.objects.select_for_update().filter(tenant=invitation.tenant, user=user).first()
    if membership and membership.is_primary:
        raise BusinessValidationError('The primary administrator account cannot accept an employee invitation.')
    if membership and membership.is_active:
        raise BusinessValidationError('This account already has active access to this organization.')
    if membership:
        membership.role = invitation.role
        membership.is_active = True
        membership.is_primary = False
        membership.save(update_fields=['role', 'is_active', 'is_primary', 'updated_at'])
    else:
        TenantUser.objects.create(
            tenant=invitation.tenant,
            user=user,
            role=invitation.role,
            is_primary=False,
            is_active=True,
        )

    employee.user = user
    employee.save(update_fields=['user', 'updated_at'])
    invitation.status = EmployeeInvitation.Status.ACCEPTED
    invitation.accepted_at = timezone.now()
    invitation.save(update_fields=['status', 'accepted_at', 'updated_at'])
    AuditService.record(
        action='EMPLOYEE_INVITATION_ACCEPTED',
        actor=user,
        tenant=invitation.tenant,
        target_type='Employee',
        target_id=str(employee.id),
        after_snapshot={'email': employee.email, 'role': invitation.role.code},
    )
    return user, invitation
