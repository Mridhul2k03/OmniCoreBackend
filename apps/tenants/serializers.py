import uuid
from rest_framework import serializers
from django.contrib.auth import get_user_model
from apps.tenants.models import Tenant, TenantUser, Role, Permission, Vertical, TenantStatus
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
    tenant_id = serializers.CharField(required=False, allow_blank=True)
    slug = serializers.SlugField(required=False, allow_blank=True)
    status = serializers.CharField(required=False, default=TenantStatus.ACTIVE)

    class Meta:
        model = Tenant
        fields = [
            'id', 'tenant_id', 'company_name', 'slug', 'email', 'phone',
            'address', 'logo', 'status', 'package', 'package_name',
            'verticals', 'activated_at', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'activated_at', 'created_at', 'updated_at']

    def validate_tenant_id(self, value):
        if value and str(value).strip():
            val = str(value).strip()
            qs = Tenant.objects.filter(tenant_id__iexact=val)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError("A tenant with this tenant_id already exists.")
            return val
        return ""

    def validate_slug(self, value):
        if value and str(value).strip():
            val = str(value).strip()
            qs = Tenant.objects.filter(slug__iexact=val)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError("A tenant with this slug already exists.")
            return val
        return ""

    def create(self, validated_data):
        import random, string
        from django.utils.text import slugify
        from django.utils import timezone

        if not validated_data.get('tenant_id'):
            for _ in range(30):
                candidate = f"OCT-{''.join(random.choices(string.digits, k=6))}"
                if not Tenant.objects.filter(tenant_id=candidate).exists():
                    validated_data['tenant_id'] = candidate
                    break
            if not validated_data.get('tenant_id'):
                validated_data['tenant_id'] = f"OCT-{uuid.uuid4().hex[:8].upper()}"

        if not validated_data.get('slug'):
            company_name = validated_data.get('company_name', 'tenant')
            base_slug = slugify(company_name) or 'tenant'
            candidate = base_slug
            counter = 1
            while Tenant.objects.filter(slug=candidate).exists():
                candidate = f"{base_slug}-{counter}"
                counter += 1
            validated_data['slug'] = candidate

        status_val = validated_data.get('status') or TenantStatus.ACTIVE
        validated_data['status'] = status_val
        if status_val == TenantStatus.ACTIVE and not validated_data.get('activated_at'):
            validated_data['activated_at'] = timezone.now()

        return super().create(validated_data)



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
