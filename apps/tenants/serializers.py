from rest_framework import serializers
from django.contrib.auth import get_user_model
from apps.tenants.models import Tenant, TenantUser, Role, Permission, Vertical
from apps.subscriptions.models import Package, Addon

User = get_user_model()


class VerticalSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vertical
        fields = ['id', 'code', 'name', 'description', 'is_active']


class RoleSerializer(serializers.ModelSerializer):
    permissions = serializers.SerializerMethodField()

    class Meta:
        model = Role
        fields = ['id', 'code', 'name', 'description', 'is_system_role', 'permissions']

    def get_permissions(self, obj):
        return list(obj.role_permissions.values_list('permission__code', flat=True))


class PermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Permission
        fields = ['id', 'code', 'name', 'module', 'description']


class TenantSerializer(serializers.ModelSerializer):
    verticals = VerticalSerializer(many=True, read_only=True)
    package_name = serializers.CharField(source='package.name', read_only=True)

    class Meta:
        model = Tenant
        fields = [
            'id', 'tenant_id', 'company_name', 'slug', 'email', 'phone',
            'address', 'logo', 'status', 'package', 'package_name',
            'verticals', 'activated_at', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'tenant_id', 'slug', 'status', 'activated_at', 'created_at', 'updated_at']


class TenantUserSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_name = serializers.CharField(source='user.full_name', read_only=True)
    role_name = serializers.CharField(source='role.name', read_only=True)
    permissions = serializers.SerializerMethodField()

    class Meta:
        model = TenantUser
        fields = [
            'id', 'user', 'user_email', 'user_name', 'role', 'role_name',
            'is_primary', 'is_active', 'permissions', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']

    def get_permissions(self, obj):
        return obj.get_all_permissions()


class TenantProvisionSerializer(serializers.Serializer):
    company_name = serializers.CharField(max_length=255, required=True)
    admin_email = serializers.EmailField(required=True)
    admin_password = serializers.CharField(write_only=True, required=True, min_length=8)
    admin_first_name = serializers.CharField(max_length=100, default='Admin')
    admin_last_name = serializers.CharField(max_length=100, default='User')
    package_code = serializers.CharField(default='CORPORATE')
    addon_codes = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    vertical_codes = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    phone = serializers.CharField(max_length=30, required=False, allow_blank=True)
    address = serializers.CharField(required=False, allow_blank=True)
    billing_cycle = serializers.ChoiceField(choices=['MONTHLY', 'YEARLY'], default='MONTHLY')
