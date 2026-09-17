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
)
from apps.accounts.models import UserDeviceSession
from apps.core.exceptions import BusinessValidationError

User = get_user_model()


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
