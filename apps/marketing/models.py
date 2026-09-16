import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _
from apps.core.models import TenantOwnedModel


class CampaignStatus(models.TextChoices):
    DRAFT = 'DRAFT', _('Draft')
    ACTIVE = 'ACTIVE', _('Active')
    PAUSED = 'PAUSED', _('Paused')
    COMPLETED = 'COMPLETED', _('Completed')


class Campaign(TenantOwnedModel):
    name = models.CharField(max_length=200)
    campaign_type = models.CharField(max_length=50, default='DIGITAL')
    start_date = models.DateField()
    end_date = models.DateField()
    budget = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    spend = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    status = models.CharField(max_length=30, choices=CampaignStatus.choices, default=CampaignStatus.DRAFT)

    def __str__(self):
        return self.name


class Promotion(TenantOwnedModel):
    promo_code = models.CharField(max_length=50, db_index=True)
    discount_type = models.CharField(max_length=20, default='PERCENTAGE')  # PERCENTAGE, FIXED
    discount_value = models.DecimalField(max_digits=10, decimal_places=2)
    valid_from = models.DateField()
    valid_to = models.DateField()
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('tenant', 'promo_code')


class LeadSource(TenantOwnedModel):
    name = models.CharField(max_length=100)
    category = models.CharField(max_length=50, default='ORGANIC')
    cost_per_lead = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)


class CampaignMetric(TenantOwnedModel):
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name='metrics')
    impressions = models.PositiveIntegerField(default=0)
    clicks = models.PositiveIntegerField(default=0)
    leads_generated = models.PositiveIntegerField(default=0)
    conversions = models.PositiveIntegerField(default=0)


class SocialPlatform(models.TextChoices):
    FACEBOOK = 'FACEBOOK', _('Facebook')
    INSTAGRAM = 'INSTAGRAM', _('Instagram')
    LINKEDIN = 'LINKEDIN', _('LinkedIn')
    TWITTER_X = 'TWITTER_X', _('X / Twitter')
    GOOGLE_ADS = 'GOOGLE_ADS', _('Google Ads')
    WHATSAPP = 'WHATSAPP', _('WhatsApp Business')


class SocialPostStatus(models.TextChoices):
    DRAFT = 'DRAFT', _('Draft')
    SCHEDULED = 'SCHEDULED', _('Scheduled')
    PUBLISHED = 'PUBLISHED', _('Published')
    FAILED = 'FAILED', _('Failed')


class SocialChannel(TenantOwnedModel):
    platform = models.CharField(max_length=30, choices=SocialPlatform.choices)
    name = models.CharField(max_length=150)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']
        unique_together = ('tenant', 'platform', 'name')

    def __str__(self):
        return f"{self.name} ({self.platform})"


class SocialAccount(TenantOwnedModel):
    """
    Linked tenant external social media account.
    API secrets and OAuth tokens are cryptographically secured.
    """
    channel = models.ForeignKey(SocialChannel, on_delete=models.CASCADE, related_name='accounts')
    account_name = models.CharField(max_length=150)
    account_id = models.CharField(max_length=150, db_index=True)
    encrypted_credentials = models.TextField(help_text="Cryptographically secured API tokens and OAuth secrets")
    is_connected = models.BooleanField(default=True)

    class Meta:
        ordering = ['account_name']
        unique_together = ('tenant', 'account_id')

    def __str__(self):
        return f"{self.account_name} [{self.channel.platform}]"


class SocialCampaign(TenantOwnedModel):
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name='social_campaigns')
    social_channel = models.ForeignKey(SocialChannel, on_delete=models.CASCADE, related_name='social_campaigns')
    external_campaign_id = models.CharField(max_length=150, blank=True)
    daily_budget = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    status = models.CharField(max_length=30, default='ACTIVE')

    class Meta:
        unique_together = ('tenant', 'campaign', 'social_channel')


class SocialPost(TenantOwnedModel):
    social_account = models.ForeignKey(SocialAccount, on_delete=models.CASCADE, related_name='posts')
    social_campaign = models.ForeignKey(SocialCampaign, null=True, blank=True, on_delete=models.SET_NULL, related_name='posts')
    content = models.TextField()
    media_urls = models.JSONField(default=list, blank=True)
    scheduled_at = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=30, choices=SocialPostStatus.choices, default=SocialPostStatus.DRAFT)
    external_post_id = models.CharField(max_length=150, blank=True)
    performance = models.JSONField(default=dict, blank=True)  # {"impressions": 0, "clicks": 0, "engagements": 0}

