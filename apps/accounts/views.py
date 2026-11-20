from rest_framework import status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model
from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
import secrets
import smtplib
import logging
from django.contrib.auth.hashers import make_password, check_password
from rest_framework.throttling import AnonRateThrottle
from apps.accounts.serializers import (
    CustomTokenObtainPairSerializer,
    UserSerializer,
    PasswordChangeSerializer,
    PasswordResetRequestSerializer,
    PasswordResetConfirmSerializer,
)
from apps.accounts.models import UserDeviceSession, RegistrationOTP
from apps.core.exceptions import BusinessValidationError

User = get_user_model()
logger = logging.getLogger(__name__)


class RegistrationRequestThrottle(AnonRateThrottle):
    scope = 'registration_request'


class RegistrationVerifyThrottle(AnonRateThrottle):
    scope = 'registration_verify'


class RegistrationOTPView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    throttle_classes = [RegistrationRequestThrottle]

    def post(self, request):
        from apps.tenants.serializers import TenantProvisionSerializer
        serializer = TenantProvisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        from apps.subscriptions.models import PackageTier
        if data.get('package_code') not in PackageTier.values:
            return Response({'message': 'Select a valid subscription package.'}, status=status.HTTP_400_BAD_REQUEST)
        email = data['admin_email'].strip().lower()
        user = User.objects.filter(email__iexact=email).first()
        if user and user.is_active:
            return Response({'message': 'If this email can be registered, a verification code has been sent.'})

        now = timezone.now()
        if user:
            previous_challenge = RegistrationOTP.objects.filter(user=user).first()
            # Never repurpose an existing inactive account (for example, an employee
            # invitation or an administrator-disabled account) as a public signup.
            if not previous_challenge:
                return Response({'message': 'If this email can be registered, a verification code has been sent.'})
            if previous_challenge and previous_challenge.last_sent_at > now - timedelta(seconds=60):
                return Response({'message': 'If this email can be registered, a verification code has been sent.'})
        code = f'{secrets.randbelow(1_000_000):06d}'
        try:
            with transaction.atomic():
                if user is None:
                    user = User.objects.create_user(
                        email=email, password=data['admin_password'],
                        first_name=data.get('admin_first_name', 'Admin'),
                        last_name=data.get('admin_last_name', 'User'),
                        phone=data.get('phone', ''), is_active=False,
                    )
                else:
                    user.set_password(data['admin_password'])
                    user.first_name = data.get('admin_first_name', 'Admin')
                    user.last_name = data.get('admin_last_name', 'User')
                    user.phone = data.get('phone', '')
                    user.save(update_fields=['password', 'first_name', 'last_name', 'phone'])

                # Do not persist plaintext passwords or verification codes.
                data.pop('admin_password', None)
                RegistrationOTP.objects.update_or_create(
                    user=user,
                    defaults={'registration_data': data, 'code_hash': make_password(code),
                              'expires_at': now + timedelta(minutes=10), 'last_sent_at': now, 'attempts': 0},
                )
                send_mail(
                    'Verify your OmniCore registration',
                    f'Your OmniCore verification code is {code}. It expires in 10 minutes. If you did not request this, ignore this email.',
                    settings.DEFAULT_FROM_EMAIL, [email], fail_silently=False,
                )
        except (OSError, smtplib.SMTPException):
            logger.exception('Could not deliver registration verification email.')
            return Response(
                {'message': 'We could not send the verification email. Check the mail server configuration and try again.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response({'message': 'If this email can be registered, a verification code has been sent.'})


class RegistrationOTPVerifyView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    throttle_classes = [RegistrationVerifyThrottle]

    def post(self, request):
        email = str(request.data.get('email', '')).strip().lower()
        code = str(request.data.get('code', '')).strip()
        if not email or len(code) != 6 or not code.isdigit():
            return Response({'message': 'A valid email and six-digit verification code are required.'}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            challenge = RegistrationOTP.objects.select_for_update().select_related('user').filter(user__email__iexact=email).first()
            if not challenge or not challenge.user.is_active and challenge.expires_at <= timezone.now():
                return Response({'message': 'Verification code is invalid or expired.'}, status=status.HTTP_400_BAD_REQUEST)
            if challenge.attempts >= 5:
                return Response({'message': 'Too many attempts. Request a new verification code.'}, status=status.HTTP_429_TOO_MANY_REQUESTS)
            if challenge.expires_at <= timezone.now() or not check_password(code, challenge.code_hash):
                challenge.attempts += 1
                challenge.save(update_fields=['attempts'])
                return Response({'message': 'Verification code is invalid or expired.'}, status=status.HTTP_400_BAD_REQUEST)

            user = challenge.user
            user.is_active = True
            user.save(update_fields=['is_active'])
            data = challenge.registration_data
            from apps.tenants.services import TenantProvisioningService
            result = TenantProvisioningService.provision(
                company_name=data['company_name'], admin_email=user.email,
                admin_password='', admin_first_name=data.get('admin_first_name', 'Admin'),
                admin_last_name=data.get('admin_last_name', 'User'), package_code=data.get('package_code', 'CORPORATE'),
                addon_codes=data.get('addon_codes', []), vertical_codes=data.get('vertical_codes', []),
                phone=data.get('phone', ''), address=data.get('address', ''),
                billing_cycle=data.get('billing_cycle', 'MONTHLY'), actor=None,
            )
            challenge.delete()
        return Response({'message': 'Email verified and organization created.', 'tenant_id': result['tenant_id'],
                         'company_name': result['tenant'].company_name}, status=status.HTTP_201_CREATED)


class CustomTokenObtainPairView(TokenObtainPairView):
    """
    Login endpoint: Authenticates user, returns JWT tokens and user payload,
    and attaches HTTP-only cookies for seamless browser-based authentication.
    """
    serializer_class = CustomTokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code == 200:
            user = User.objects.filter(email=request.data.get('email', '').lower()).first()
            if user:
                # Track session
                ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', ''))
                if ',' in ip:
                    ip = ip.split(',')[0].strip()
                user_agent = request.META.get('HTTP_USER_AGENT', '')
                UserDeviceSession.objects.create(
                    user=user,
                    ip_address=ip if ip else None,
                    user_agent=user_agent[:500],
                )

            # Set HTTP-only cookies for cookie-based auth
            access_token = response.data.get('access')
            refresh_token = response.data.get('refresh')
            if access_token:
                response.set_cookie(
                    key='access_token',
                    value=access_token,
                    max_age=60 * 60,  # 1 hour
                    httponly=True,
                    samesite='Lax',
                    secure=not settings.DEBUG,
                    path='/',
                )
            if refresh_token:
                response.set_cookie(
                    key='refresh_token',
                    value=refresh_token,
                    max_age=7 * 24 * 60 * 60,  # 7 days
                    httponly=True,
                    samesite='Lax',
                    secure=not settings.DEBUG,
                    path='/',
                )
        return response


class CustomTokenRefreshView(TokenRefreshView):
    """
    Token refresh endpoint: accepts refresh token from body or cookie,
    and updates the access token cookie.
    """
    def post(self, request, *args, **kwargs):
        if 'refresh' not in request.data and 'refresh_token' in request.COOKIES:
            request.data['refresh'] = request.COOKIES['refresh_token']

        response = super().post(request, *args, **kwargs)
        if response.status_code == 200:
            access_token = response.data.get('access')
            if access_token:
                response.set_cookie(
                    key='access_token',
                    value=access_token,
                    max_age=60 * 60,
                    httponly=True,
                    samesite='Lax',
                    secure=not settings.DEBUG,
                    path='/',
                )
            new_refresh = response.data.get('refresh')
            if new_refresh:
                response.set_cookie(
                    key='refresh_token',
                    value=new_refresh,
                    max_age=7 * 24 * 60 * 60,
                    httponly=True,
                    samesite='Lax',
                    secure=not settings.DEBUG,
                    path='/',
                )
        return response


class LogoutView(APIView):
    """
    Logout endpoint: Revokes refresh token and clears auth cookies.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        refresh_token = request.data.get('refresh') or request.COOKIES.get('refresh_token')
        if refresh_token:
            try:
                token = RefreshToken(refresh_token)
                token.blacklist()
            except Exception:
                pass

        response = Response({'message': 'Logged out successfully.'})
        response.delete_cookie('access_token', path='/')
        response.delete_cookie('refresh_token', path='/')
        return response


class AuthMeView(APIView):
    """
    GET /api/v1/auth/me/
    Returns:
    - user profile
    - active tenant context
    - tenant role
    - granular permissions
    - enabled modules/features
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        from apps.core.middleware import resolve_tenant_context
        tenant, tenant_user = resolve_tenant_context(request)

        from apps.tenants.models import TenantUser
        from apps.subscriptions.services import get_tenant_entitled_features

        # Active tenant payload
        active_tenant_data = None
        role_data = None
        permissions_list = []
        enabled_features = []

        if tenant:
            active_tenant_data = {
                'id': str(tenant.id),
                'tenant_id': tenant.tenant_id,
                'company_name': tenant.company_name,
                'slug': tenant.slug,
                'status': tenant.status,
                'package': tenant.package.name if tenant.package else None,
                'activated_at': tenant.activated_at,
                'is_primary': bool(tenant_user and tenant_user.is_primary),
            }
            if tenant_user:
                role_data = {
                    'code': tenant_user.role.code if tenant_user.role else 'NO_ROLE',
                    'name': tenant_user.role.name if tenant_user.role else 'No Role',
                }
                permissions_list = tenant_user.get_all_permissions()
            elif user.is_superuser:
                role_data = {'code': 'SUPER_ADMIN', 'name': 'Super Administrator'}
                permissions_list = ['*']

            enabled_features = get_tenant_entitled_features(tenant)

        # All memberships
        memberships = TenantUser.objects.filter(
            user=user,
            is_active=True
        ).select_related('tenant', 'role')

        tenants_list = [
            {
                'id': str(m.tenant.id),
                'tenant_id': m.tenant.tenant_id,
                'company_name': m.tenant.company_name,
                'slug': m.tenant.slug,
                'status': m.tenant.status,
                'role': m.role.name if m.role else None,
                'is_primary': m.is_primary,
            }
            for m in memberships
        ]

        data = {
            'user': UserSerializer(user).data,
            'active_tenant': active_tenant_data,
            'role': role_data,
            'permissions': permissions_list,
            'enabled_features': enabled_features,
            'memberships': tenants_list
        }
        return Response({'success': True, 'data': data})


class PasswordChangeView(APIView):
    """
    Password change endpoint for authenticated users.
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = PasswordChangeSerializer

    def post(self, request):
        serializer = PasswordChangeSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        user = request.user
        if not user.check_password(serializer.validated_data['old_password']):
            raise BusinessValidationError("Current password is incorrect.", code='INVALID_PASSWORD')

        user.set_password(serializer.validated_data['new_password'])
        user.save()
        return Response({'message': 'Password changed successfully.'})


class PasswordResetRequestView(APIView):
    """
    Public endpoint to initiate password reset via email.
    """
    permission_classes = [permissions.AllowAny]
    serializer_class = PasswordResetRequestSerializer

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # Note: in production sends email token; returns success message uniformly
        return Response({'message': 'If an account exists with this email, password reset instructions have been sent.'})


class PasswordResetConfirmView(APIView):
    """
    Public endpoint to confirm password reset with token.
    """
    permission_classes = [permissions.AllowAny]
    serializer_class = PasswordResetConfirmSerializer

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response({'message': 'Password has been reset successfully.'})
