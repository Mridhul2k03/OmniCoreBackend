from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
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


class MarketingViewSet(TenantModelViewSet):
    required_permission = 'marketing.view'


class CampaignViewSet(MarketingViewSet):
    queryset = Campaign.objects.all().prefetch_related('metrics')
    serializer_class = CampaignSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['status', 'campaign_type']
    search_fields = ['name']

    @action(detail=True, methods=['patch'])
    def metrics(self, request, pk=None):
        campaign = self.get_object()
        metric, _ = CampaignMetric.objects.get_or_create(tenant=request.tenant, campaign=campaign)
        metric_serializer = CampaignMetricSerializer(metric, data=request.data, partial=True)
        metric_serializer.is_valid(raise_exception=True)
        metric_serializer.save(tenant=request.tenant, campaign=campaign)

        campaign_updates = {}
        for field in ('spend', 'attributed_revenue'):
            if field in request.data:
                campaign_updates[field] = request.data[field]
        if campaign_updates:
            campaign_serializer = self.get_serializer(campaign, data=campaign_updates, partial=True)
            campaign_serializer.is_valid(raise_exception=True)
            campaign_serializer.save()

        campaign.refresh_from_db()
        return Response(CampaignSerializer(campaign, context=self.get_serializer_context()).data)


class PromotionViewSet(MarketingViewSet):
    queryset = Promotion.objects.all()
    serializer_class = PromotionSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['is_active']


class LeadSourceViewSet(MarketingViewSet):
    queryset = LeadSource.objects.all()
    serializer_class = LeadSourceSerializer


class SocialChannelViewSet(MarketingViewSet):
    from apps.marketing.models import SocialChannel
    from apps.marketing.serializers import SocialChannelSerializer
    queryset = SocialChannel.objects.all()
    serializer_class = SocialChannelSerializer
    filterset_fields = ['platform', 'is_active']
    search_fields = ['name']


class SocialAccountViewSet(MarketingViewSet):
    from apps.marketing.models import SocialAccount
    from apps.marketing.serializers import SocialAccountSerializer
    queryset = SocialAccount.objects.all().select_related('channel')
    serializer_class = SocialAccountSerializer
    filterset_fields = ['channel', 'is_connected']
    search_fields = ['account_name', 'account_id']


class SocialCampaignViewSet(MarketingViewSet):
    from apps.marketing.models import SocialCampaign
    from apps.marketing.serializers import SocialCampaignSerializer
    queryset = SocialCampaign.objects.all().select_related('campaign', 'social_channel')
    serializer_class = SocialCampaignSerializer
    filterset_fields = ['status', 'social_channel']


class SocialPostViewSet(MarketingViewSet):
    from apps.marketing.models import SocialPost
    from apps.marketing.serializers import SocialPostSerializer
    queryset = SocialPost.objects.all().select_related('social_account__channel', 'social_campaign__campaign')
    serializer_class = SocialPostSerializer
    filterset_fields = ['status', 'social_account']

