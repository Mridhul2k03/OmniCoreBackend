from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.marketing.views import (
    CampaignViewSet, PromotionViewSet, LeadSourceViewSet,
    SocialChannelViewSet, SocialAccountViewSet, SocialCampaignViewSet, SocialPostViewSet
)

router = DefaultRouter()
router.register('campaigns', CampaignViewSet, basename='campaigns')
router.register('promotions', PromotionViewSet, basename='promotions')
router.register('lead-sources', LeadSourceViewSet, basename='lead_sources')
router.register('social/channels', SocialChannelViewSet, basename='social-channels')
router.register('social/accounts', SocialAccountViewSet, basename='social-accounts')
router.register('social/campaigns', SocialCampaignViewSet, basename='social-campaigns')
router.register('social/posts', SocialPostViewSet, basename='social-posts')

app_name = 'marketing'

urlpatterns = [
    path('marketing/', include(router.urls)),
]

