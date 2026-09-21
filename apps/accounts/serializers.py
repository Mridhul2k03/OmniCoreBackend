from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.db import transaction

User = get_user_model()

# ---------------------------------------------------------------------------
# MRR pricing map — authoritative base monthly prices per tier
# ---------------------------------------------------------------------------
TIER_MRR_MAP = {
    'BASIC': 149.00,
    'STANDARD': 399.00,
    'CORPORATE': 899.00,
    'ENTERPRISE': 1899.00,
}


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Custom JWT serializer that embeds tenant memberships and platform roles.
    """
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['email'] = user.email
        token['full_name'] = user.full_name
        token['is_platform_admin'] = user.is_platform_admin
        token['platform_role'] = user.platform_role

        # Embed tenant context from primary membership
        from apps.tenants.models import TenantUser
        primary_membership = TenantUser.objects.filter(
            user=user, is_active=True, is_primary=True
        ).select_related('tenant', 'role').first()

        if primary_membership:
            token['tenant_id'] = str(primary_membership.tenant.id)
            token['role'] = primary_membership.role.code if primary_membership.role else None
        else:
            token['tenant_id'] = None
            token['role'] = 'super_admin' if user.is_platform_admin else None

        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        user = self.user

        # Fetch tenant memberships
        from apps.tenants.models import TenantUser
        memberships = TenantUser.objects.filter(
            user=user,
            is_active=True
        ).select_related('tenant', 'role')

        tenants_data = []
        for m in memberships:
            tenants_data.append({
                'id': str(m.tenant.id),
                'tenant_id': m.tenant.tenant_id,
                'company_name': m.tenant.company_name,
                'slug': m.tenant.slug,
                'status': m.tenant.status,
                'role': m.role.name if m.role else None,
                'role_code': m.role.code if m.role else None,
                'permissions': m.get_all_permissions(),
                'is_primary': m.is_primary
            })

        data['user'] = {
            'id': str(user.id),
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'full_name': user.full_name,
            'is_platform_admin': user.is_platform_admin,
            'platform_role': user.platform_role,
        }
        data['tenants'] = tenants_data
        return data


class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)

    class Meta:
        model = User
        fields = [
            'id', 'email', 'first_name', 'last_name', 'full_name',
            'phone', 'avatar', 'is_platform_admin', 'platform_role',
            'is_mfa_enabled', 'date_joined'
        ]
        read_only_fields = ['id', 'is_platform_admin', 'platform_role', 'date_joined']


class PasswordChangeSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True)

    def validate_new_password(self, value):
        validate_password(value, self.context['request'].user)
        return value


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)


class PasswordResetConfirmSerializer(serializers.Serializer):
    token = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True)

    def validate_new_password(self, value):
        validate_password(value)
        return value


class RegisterSerializer(serializers.Serializer):
    """
    Registration serializer for the 2-step onboarding flow (Step 1).
    Creates a Tenant + Admin User atomically, or a platform super admin.
    """
    company_name = serializers.CharField(max_length=255, required=True)
    email = serializers.EmailField(required=True)
    password = serializers.CharField(write_only=True, required=True, min_length=8)
    first_name = serializers.CharField(max_length=100, default='Admin', required=False)
    last_name = serializers.CharField(max_length=100, default='User', required=False)
    phone = serializers.CharField(max_length=30, required=False, allow_blank=True, default='')
    is_super_admin = serializers.BooleanField(default=False, required=False)
    package_tier = serializers.CharField(max_length=32, default='standard', required=False)

    def validate_email(self, value):
        email = value.lower().strip()
        if User.objects.filter(email=email).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return email

    def validate_password(self, value):
        validate_password(value)
        return value

    def validate_package_tier(self, value):
        from apps.subscriptions.models import PackageTier
        normalized = value.upper()
        valid_codes = [c[0] for c in PackageTier.choices]
        if normalized not in valid_codes:
            raise serializers.ValidationError(
                f"Invalid package tier. Must be one of: {', '.join(c.lower() for c in valid_codes)}"
            )
        return normalized

    def create(self, validated_data):
        is_super_admin = validated_data.get('is_super_admin', False)
        email = validated_data['email']
        password = validated_data['password']
        first_name = validated_data.get('first_name', 'Admin')
        last_name = validated_data.get('last_name', 'User')
        phone = validated_data.get('phone', '')
        company_name = validated_data['company_name']
        package_tier = validated_data.get('package_tier', 'STANDARD')

        with transaction.atomic():
            if is_super_admin:
                # ── Platform Super Admin (no tenant) ──
                from apps.accounts.models import PlatformRole
                user = User.objects.create_user(
                    email=email,
                    password=password,
                    first_name=first_name,
                    last_name=last_name,
                    phone=phone,
                    is_staff=True,
                    is_superuser=True,
                    is_platform_admin=True,
                    platform_role=PlatformRole.SUPER_ADMIN,
                )
                tokens = RefreshToken.for_user(user)
                return {
                    'user': user,
                    'tenant': None,
                    'access': str(tokens.access_token),
                    'refresh': str(tokens),
                }
            else:
                # ── Tenant Admin + Organization Provisioning ──
                from apps.tenants.services import TenantProvisioningService
                result = TenantProvisioningService.provision(
                    company_name=company_name,
                    admin_email=email,
                    admin_password=password,
                    admin_first_name=first_name,
                    admin_last_name=last_name,
                    package_code=package_tier,
                    phone=phone,
                    billing_cycle='MONTHLY',
                )
                user = result['admin_user']
                tenant = result['tenant']
                tokens = RefreshToken.for_user(user)
                return {
                    'user': user,
                    'tenant': tenant,
                    'access': str(tokens.access_token),
                    'refresh': str(tokens),
                }
