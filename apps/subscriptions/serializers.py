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
