from rest_framework import serializers
from apps.subscriptions.models import Feature, Package, Addon, Subscription, TenantFeature


class FeatureSerializer(serializers.ModelSerializer):
    class Meta:
        model = Feature
        fields = ['id', 'code', 'name', 'description', 'category']


class PackageSerializer(serializers.ModelSerializer):
    features = FeatureSerializer(many=True, read_only=True)

    class Meta:
        model = Package
        fields = [
            'id', 'code', 'name', 'description', 'price_monthly',
            'price_yearly', 'max_vehicles', 'max_users', 'is_active', 'features'
        ]


class AddonSerializer(serializers.ModelSerializer):
    features = FeatureSerializer(many=True, read_only=True)

    class Meta:
        model = Addon
        fields = ['id', 'code', 'name', 'description', 'monthly_price', 'is_active', 'features']


class SubscriptionSerializer(serializers.ModelSerializer):
    package = PackageSerializer(read_only=True)
    addons = AddonSerializer(many=True, read_only=True)

    class Meta:
        model = Subscription
        fields = [
            'id', 'package', 'addons', 'billing_cycle', 'status',
            'current_period_start', 'current_period_end', 'trial_end', 'auto_renew'
        ]
        read_only_fields = ['id', 'status', 'current_period_start', 'current_period_end', 'trial_end']


class ActivatePlanSerializer(serializers.Serializer):
    """
    Serializer for Step 2 of onboarding: plan activation / billing cycle selection.
    """
    tenant_id = serializers.CharField(required=True, help_text="Tenant UUID or tenant_id string")
    package_tier = serializers.CharField(required=True, max_length=32)
    billing_cycle = serializers.ChoiceField(
        choices=[('monthly', 'Monthly'), ('annually', 'Annually')],
        default='monthly',
    )

    def validate_package_tier(self, value):
        from apps.subscriptions.models import PackageTier
        normalized = value.upper()
        valid_codes = [c[0] for c in PackageTier.choices]
        if normalized not in valid_codes:
            raise serializers.ValidationError(
                f"Invalid package tier. Must be one of: {', '.join(c.lower() for c in valid_codes)}"
            )
        return normalized

    def validate_billing_cycle(self, value):
        """Normalize to uppercase for the BillingCycle model enum."""
        mapping = {'monthly': 'MONTHLY', 'annually': 'YEARLY'}
        return mapping.get(value.lower(), 'MONTHLY')

