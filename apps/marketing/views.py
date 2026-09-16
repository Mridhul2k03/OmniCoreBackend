from rest_framework import status
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter

from apps.core.viewsets import TenantModelViewSet
from apps.marketing.models import Campaign, Promotion, LeadSource, CampaignMetric
from apps.marketing.serializers import (
    CampaignSerializer,
    PromotionSerializer,
    LeadSourceSerializer,
    CampaignMetricSerializer,
)


class CampaignViewSet(TenantModelViewSet):
    queryset = Campaign.objects.all().prefetch_related('metrics')
    serializer_class = CampaignSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['status', 'campaign_type']
    search_fields = ['name']


class PromotionViewSet(TenantModelViewSet):
    queryset = Promotion.objects.all()
    serializer_class = PromotionSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['is_active']


class LeadSourceViewSet(TenantModelViewSet):
    queryset = LeadSource.objects.all()
    serializer_class = LeadSourceSerializer


class SocialChannelViewSet(TenantModelViewSet):
    from apps.marketing.models import SocialChannel
    from apps.marketing.serializers import SocialChannelSerializer
    queryset = SocialChannel.objects.all()
    serializer_class = SocialChannelSerializer
    filterset_fields = ['platform', 'is_active']
    search_fields = ['name']


class SocialAccountViewSet(TenantModelViewSet):
    from apps.marketing.models import SocialAccount
    from apps.marketing.serializers import SocialAccountSerializer
    queryset = SocialAccount.objects.all().select_related('channel')
    serializer_class = SocialAccountSerializer
    filterset_fields = ['channel', 'is_connected']
    search_fields = ['account_name', 'account_id']


class SocialCampaignViewSet(TenantModelViewSet):
    from apps.marketing.models import SocialCampaign
    from apps.marketing.serializers import SocialCampaignSerializer
    queryset = SocialCampaign.objects.all().select_related('campaign', 'social_channel')
    serializer_class = SocialCampaignSerializer
    filterset_fields = ['status', 'social_channel']


class SocialPostViewSet(TenantModelViewSet):
    from apps.marketing.models import SocialPost
    from apps.marketing.serializers import SocialPostSerializer
    queryset = SocialPost.objects.all().select_related('social_account', 'social_campaign')
    serializer_class = SocialPostSerializer
    filterset_fields = ['status', 'social_account']

