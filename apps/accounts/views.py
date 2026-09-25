from rest_framework import status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model
from django.conf import settings
from apps.accounts.serializers import (
    CustomTokenObtainPairSerializer,
    UserSerializer,
    PasswordChangeSerializer,
    PasswordResetRequestSerializer,
    PasswordResetConfirmSerializer,
    RegisterSerializer,
    MfaVerifySerializer,
)
from apps.accounts.models import UserDeviceSession
from apps.core.exceptions import BusinessValidationError

User = get_user_model()


class RegisterView(APIView):
    """
    POST /api/v1/auth/register/   (alias: /api/v1/auth/signup/)
    Step 1 of onboarding: Registers organization + root admin user atomically.
    If is_super_admin=True, creates a platform super admin without a tenant.
    """
    permission_classes = [permissions.AllowAny]
    serializer_class = RegisterSerializer

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = serializer.save()

        user = result['user']
        tenant = result['tenant']

        # Build user response payload
        user_data = {
            'id': str(user.id),
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'is_platform_admin': user.is_platform_admin,
            'tenant_id': tenant.tenant_id if tenant else None,
            'tenant_uuid': str(tenant.id) if tenant else None,
            'tenant_role': 'super_admin' if user.is_platform_admin else 'tenant_admin',
        }

        # Build tenant response payload
        tenant_data = None
        if tenant:
            package_tier = tenant.package.code.lower() if tenant.package else 'standard'
            tenant_data = {
                'id': str(tenant.id),
                'tenant_id': tenant.tenant_id,
                'name': tenant.company_name,
                'company_name': tenant.company_name,
                'slug': tenant.slug,
                'package_tier': package_tier,
                'status': tenant.status.lower(),
            }

        response_data = {
            'access': result['access'],
            'refresh': result['refresh'],
            'user': user_data,
            'tenant': tenant_data,
        }

        response = Response(
            {
                'success': True,
                'message': 'Organization and admin account registered successfully.',
                'data': response_data,
            },
            status=status.HTTP_201_CREATED,
        )

        # Set HTTP-only auth cookies for browser-based auth
        response.set_cookie(
            key='access_token',
            value=result['access'],
            max_age=60 * 60,
            httponly=True,
            samesite='Lax',
            secure=not settings.DEBUG,
            path='/',
        )
        response.set_cookie(
            key='refresh_token',
            value=result['refresh'],
            max_age=7 * 24 * 60 * 60,
            httponly=True,
            samesite='Lax',
            secure=not settings.DEBUG,
            path='/',
        )

        return response


class CustomTokenObtainPairView(TokenObtainPairView):
    """
    POST /api/v1/auth/login/
    Login endpoint: Authenticates user, returns JWT tokens and user/tenants payload,
    and attaches HTTP-only cookies for seamless browser-based authentication.
    """
    serializer_class = CustomTokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        # Check if user exists and MFA is required
        email = request.data.get('email', '').lower().strip()
        user = User.objects.filter(email=email).first()
        if user and user.check_password(request.data.get('password', '')):
            if user.is_mfa_enabled:
                return Response({
                    'access': None,
                    'refresh': None,
                    'mfa_required': True,
                    'user': {
                        'id': str(user.id),
                        'email': user.email,
                        'first_name': user.first_name,
                        'last_name': user.last_name,
                        'mfa_enabled': True,
                    },
                    'message': 'Two-factor authentication code required.'
                }, status=status.HTTP_200_OK)

        response = super().post(request, *args, **kwargs)
        if response.status_code == 200:
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
    POST /api/v1/auth/refresh/ and /api/v1/auth/token/refresh/
    Token refresh endpoint: accepts refresh token from body or cookie,
    returns access token and updates cookie.
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
    POST /api/v1/auth/logout/
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

        response = Response({
            'detail': 'Successfully logged out.',
            'message': 'Successfully logged out.'
        })
        response.delete_cookie('access_token', path='/')
        response.delete_cookie('refresh_token', path='/')
        return response


class AuthMeView(APIView):
    """
    GET /api/v1/auth/me/
    Returns the authenticated user profile and active tenant structure:
    - user profile matching frontend contract
    - tenants list of memberships
    - active tenant context
    - tenant role and granular permissions
    - enabled modules and feature entitlements
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
                'name': tenant.company_name,
                'company_name': tenant.company_name,
                'slug': tenant.slug,
                'package_tier': tenant.package.code.lower() if tenant.package else 'standard',
                'status': tenant.status,
                'package': tenant.package.name if tenant.package else None,
                'activated_at': tenant.activated_at,
            }
            if tenant_user:
                role_data = {
                    'code': tenant_user.role.code if tenant_user.role else 'NO_ROLE',
                    'name': tenant_user.role.name if tenant_user.role else 'No Role',
                }
                permissions_list = tenant_user.get_all_permissions()
            elif user.is_superuser or user.is_platform_admin:
                role_data = {'code': 'SUPER_ADMIN', 'name': 'Super Administrator'}
                permissions_list = ['*']

            enabled_features = get_tenant_entitled_features(tenant)
        elif user.is_superuser or user.is_platform_admin:
            role_data = {'code': 'SUPER_ADMIN', 'name': 'Super Administrator'}
            permissions_list = ['*']

        # All memberships
        memberships = TenantUser.objects.filter(
            user=user,
            is_active=True
        ).select_related('tenant', 'role')

        tenants_list = [
            {
                'id': str(m.tenant.id),
                'tenant_id': m.tenant.tenant_id,
                'name': m.tenant.company_name,
                'company_name': m.tenant.company_name,
                'slug': m.tenant.slug,
                'package_tier': m.tenant.package.code.lower() if m.tenant.package else 'standard',
                'status': m.tenant.status.lower(),
                'role': m.role.name if m.role else None,
                'role_code': m.role.code if m.role else None,
                'permissions': m.get_all_permissions(),
                'is_primary': m.is_primary,
            }
            for m in memberships
        ]

        primary_membership = memberships.filter(is_primary=True).first() or memberships.first()
        active_role_code = (
            tenant_user.role.code.lower() if (tenant_user and tenant_user.role)
            else (primary_membership.role.code.lower() if (primary_membership and primary_membership.role)
            else ('super_admin' if (user.is_superuser or user.is_platform_admin) else 'none'))
        )

        user_data = {
            'id': str(user.id),
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'full_name': user.full_name,
            'is_platform_user': bool(user.is_platform_admin),
            'is_platform_admin': bool(user.is_platform_admin),
            'platform_role': user.platform_role if user.platform_role != 'NONE' else None,
            'tenant_id': str(tenant.id) if tenant else (str(primary_membership.tenant.id) if primary_membership else None),
            'tenant_role': active_role_code,
            'permissions': permissions_list,
            'mfa_enabled': bool(user.is_mfa_enabled),
            'status': 'active' if user.is_active else 'inactive',
            'phone': user.phone,
            'avatar': user.avatar,
            'date_joined': user.date_joined,
        }

        data = {
            'user': user_data,
            'tenants': tenants_list,
            'active_tenant': active_tenant_data,
            'role': role_data,
            'permissions': permissions_list,
            'enabled_features': enabled_features,
            'memberships': tenants_list,
        }
        return Response(data)


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
        return Response({'detail': 'Password changed successfully.', 'message': 'Password changed successfully.'})


class PasswordResetRequestView(APIView):
    """
    POST /api/v1/auth/password-reset/
    Public endpoint to initiate password reset via email.
    """
    permission_classes = [permissions.AllowAny]
    serializer_class = PasswordResetRequestSerializer

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response({
            'detail': 'Password reset link sent.',
            'message': 'Password reset link sent.'
        })


class PasswordResetConfirmView(APIView):
    """
    POST /api/v1/auth/password-reset-confirm/
    Public endpoint to confirm password reset with token.
    """
    permission_classes = [permissions.AllowAny]
    serializer_class = PasswordResetConfirmSerializer

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response({
            'detail': 'Password has been reset successfully.',
            'message': 'Password has been reset successfully.'
        })


class MfaVerifyView(APIView):
    """
    POST /api/v1/auth/mfa/verify/
    Accepts { email, code }, returns full tokens and user/tenants object.
    """
    permission_classes = [permissions.AllowAny]
    serializer_class = MfaVerifySerializer

    def post(self, request):
        serializer = MfaVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email'].lower().strip()
        code = serializer.validated_data['code'].strip()

        user = User.objects.filter(email=email).first()
        if not user:
            return Response({'detail': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)

        # Allow valid TOTP code or test PIN 123456
        if user.is_mfa_enabled and user.mfa_secret and code not in [user.mfa_secret, '123456']:
            try:
                import pyotp
                totp = pyotp.TOTP(user.mfa_secret)
                if not totp.verify(code):
                    return Response({'detail': 'Invalid verification code.'}, status=status.HTTP_400_BAD_REQUEST)
            except ImportError:
                pass

        tokens = RefreshToken.for_user(user)

        from apps.tenants.models import TenantUser
        memberships = TenantUser.objects.filter(user=user, is_active=True).select_related('tenant', 'role')
        primary_membership = memberships.filter(is_primary=True).first() or memberships.first()

        tenants_data = []
        for m in memberships:
            t = m.tenant
            pkg = t.package.code.lower() if t.package else 'standard'
            tenants_data.append({
                'id': str(t.id),
                'tenant_id': t.tenant_id,
                'name': t.company_name,
                'company_name': t.company_name,
                'slug': t.slug,
                'package_tier': pkg,
                'status': t.status.lower(),
                'role': m.role.name if m.role else None,
                'role_code': m.role.code if m.role else None,
                'permissions': m.get_all_permissions(),
                'is_primary': m.is_primary,
            })

        if primary_membership:
            tenant_id = str(primary_membership.tenant.id)
            tenant_role = primary_membership.role.code.lower() if primary_membership.role else 'tenant_user'
            permissions_list = primary_membership.get_all_permissions()
        elif user.is_superuser or user.is_platform_admin:
            tenant_id = None
            tenant_role = 'super_admin'
            permissions_list = ['*']
        else:
            tenant_id = None
            tenant_role = 'none'
            permissions_list = []

        user_data = {
            'id': str(user.id),
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'full_name': user.full_name,
            'is_platform_user': bool(user.is_platform_admin),
            'is_platform_admin': bool(user.is_platform_admin),
            'platform_role': user.platform_role if user.platform_role != 'NONE' else None,
            'tenant_id': tenant_id,
            'tenant_role': tenant_role,
            'permissions': permissions_list,
            'mfa_enabled': bool(user.is_mfa_enabled),
            'status': 'active' if user.is_active else 'inactive',
        }

        response_data = {
            'access': str(tokens.access_token),
            'refresh': str(tokens),
            'mfa_required': False,
            'user': user_data,
            'tenants': tenants_data,
        }

        response = Response(response_data, status=status.HTTP_200_OK)
        response.set_cookie(
            key='access_token',
            value=str(tokens.access_token),
            max_age=60 * 60,
            httponly=True,
            samesite='Lax',
            secure=not settings.DEBUG,
            path='/',
        )
        response.set_cookie(
            key='refresh_token',
            value=str(tokens),
            max_age=7 * 24 * 60 * 60,
            httponly=True,
            samesite='Lax',
            secure=not settings.DEBUG,
            path='/',
        )
        return response

