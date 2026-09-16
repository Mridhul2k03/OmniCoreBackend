from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password

User = get_user_model()


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
