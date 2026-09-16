from rest_framework import serializers
from apps.marketing.models import Campaign, Promotion, LeadSource, CampaignMetric


class CampaignMetricSerializer(serializers.ModelSerializer):
    class Meta:
        model = CampaignMetric
        fields = ['id', 'campaign', 'impressions', 'clicks', 'leads_generated', 'conversions']


class CampaignSerializer(serializers.ModelSerializer):
    metrics = CampaignMetricSerializer(many=True, read_only=True)

    class Meta:
        model = Campaign
        fields = ['id', 'name', 'campaign_type', 'start_date', 'end_date', 'budget', 'spend', 'status', 'metrics', 'created_at']
        read_only_fields = ['id', 'created_at']


class PromotionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Promotion
        fields = ['id', 'promo_code', 'discount_type', 'discount_value', 'valid_from', 'valid_to', 'is_active', 'created_at']
        read_only_fields = ['id', 'created_at']


class LeadSourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeadSource
        fields = ['id', 'name', 'category', 'cost_per_lead', 'created_at']
        read_only_fields = ['id', 'created_at']


class SocialChannelSerializer(serializers.ModelSerializer):
    class Meta:
        from apps.marketing.models import SocialChannel
        model = SocialChannel
        fields = ['id', 'platform', 'name', 'is_active', 'created_at']
        read_only_fields = ['id', 'created_at']


class SocialAccountSerializer(serializers.ModelSerializer):
    api_key_or_token = serializers.CharField(write_only=True, required=False)

    class Meta:
        from apps.marketing.models import SocialAccount
        model = SocialAccount
        fields = ['id', 'channel', 'account_name', 'account_id', 'is_connected', 'api_key_or_token', 'created_at']
        read_only_fields = ['id', 'created_at']

    def create(self, validated_data):
        from django.core.signing import dumps
        token = validated_data.pop('api_key_or_token', '')
        validated_data['encrypted_credentials'] = dumps(token) if token else ''
        return super().create(validated_data)


class SocialCampaignSerializer(serializers.ModelSerializer):
    class Meta:
        from apps.marketing.models import SocialCampaign
        model = SocialCampaign
        fields = ['id', 'campaign', 'social_channel', 'external_campaign_id', 'daily_budget', 'status', 'created_at']
        read_only_fields = ['id', 'created_at']


class SocialPostSerializer(serializers.ModelSerializer):
    class Meta:
        from apps.marketing.models import SocialPost
        model = SocialPost
        fields = [
            'id', 'social_account', 'social_campaign', 'content', 'media_urls',
            'scheduled_at', 'published_at', 'status', 'external_post_id',
            'performance', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']

