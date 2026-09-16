from django.db import models
from django.utils.translation import gettext_lazy as _
from apps.core.models import TenantOwnedModel


class SectionType(models.TextChoices):
    HERO = 'HERO', _('Hero Banner')
    SERVICES = 'SERVICES', _('Featured Services Grid')
    ABOUT = 'ABOUT', _('About Company')
    STATS = 'STATS', _('Operational Metrics & Stats')
    BOOKING_WIDGET = 'BOOKING_WIDGET', _('Interactive Booking Widget')
    FAQ = 'FAQ', _('Frequently Asked Questions')
    TESTIMONIALS = 'TESTIMONIALS', _('Customer Testimonials')
    CTA = 'CTA', _('Call to Action')


class TenantWebsite(TenantOwnedModel):
    """
    Dynamic CMS mini-website configuration for a tenant.
    """
    site_title = models.CharField(max_length=150)
    subdomain = models.SlugField(max_length=100, unique=True, db_index=True)
    custom_domain = models.CharField(max_length=255, blank=True, null=True, unique=True)
    logo_url = models.CharField(max_length=500, blank=True)
    favicon_url = models.CharField(max_length=500, blank=True)
    company_name = models.CharField(max_length=200)
    tagline = models.CharField(max_length=255, blank=True)
    about_text = models.TextField(blank=True)
    contact_email = models.EmailField()
    contact_phone = models.CharField(max_length=30)
    address = models.TextField(blank=True)
    
    # Theme design tokens
    theme = models.JSONField(default=dict, blank=True, help_text="Custom primary, secondary colors, fonts, dark mode tokens")
    social_links = models.JSONField(default=dict, blank=True)
    enabled_verticals = models.JSONField(default=list, blank=True, help_text="e.g. ['COURIER', 'TAXI', 'BUS', 'SHUTTLE']")
    
    is_published = models.BooleanField(default=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.site_title} ({self.subdomain})"


class WebsitePage(TenantOwnedModel):
    """
    Individual navigation page of tenant mini-website.
    """
    website = models.ForeignKey(TenantWebsite, on_delete=models.CASCADE, related_name='pages')
    title = models.CharField(max_length=150)
    slug = models.SlugField(max_length=100)
    meta_description = models.CharField(max_length=255, blank=True)
    is_published = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ['order']
        unique_together = ('website', 'slug')

    def __str__(self):
        return f"{self.website.subdomain} - /{self.slug}"


class WebsiteSection(TenantOwnedModel):
    """
    Configurable modular section component on a page.
    """
    page = models.ForeignKey(WebsitePage, on_delete=models.CASCADE, related_name='sections')
    section_type = models.CharField(max_length=30, choices=SectionType.choices, default=SectionType.HERO)
    heading = models.CharField(max_length=200, blank=True)
    subheading = models.CharField(max_length=255, blank=True)
    content = models.JSONField(default=dict, blank=True)
    sequence = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ['sequence']

    def __str__(self):
        return f"{self.page.slug} -> {self.section_type} (#{self.sequence})"


class WebsiteService(TenantOwnedModel):
    """
    Vertical service offered by tenant displayed on public mini-website.
    """
    website = models.ForeignKey(TenantWebsite, on_delete=models.CASCADE, related_name='services')
    vertical = models.CharField(max_length=50, default='COURIER')
    title = models.CharField(max_length=150)
    description = models.TextField()
    icon = models.CharField(max_length=100, blank=True)
    pricing_summary = models.CharField(max_length=100, blank=True)
    is_featured = models.BooleanField(default=True)

    class Meta:
        ordering = ['title']

    def __str__(self):
        return f"{self.title} [{self.vertical}]"


class WebsiteBlogPost(TenantOwnedModel):
    """
    SEO content / blog article for tenant marketing.
    """
    website = models.ForeignKey(TenantWebsite, on_delete=models.CASCADE, related_name='posts')
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255)
    content = models.TextField()
    author_name = models.CharField(max_length=100, default='Staff')
    published_at = models.DateTimeField(null=True, blank=True)
    is_published = models.BooleanField(default=True)

    class Meta:
        ordering = ['-published_at']
        unique_together = ('website', 'slug')

    def __str__(self):
        return self.title


class WebsiteFAQ(TenantOwnedModel):
    """
    Frequently asked questions.
    """
    website = models.ForeignKey(TenantWebsite, on_delete=models.CASCADE, related_name='faqs')
    question = models.CharField(max_length=255)
    answer = models.TextField()
    category = models.CharField(max_length=100, default='General')
    sequence = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ['sequence']

    def __str__(self):
        return self.question


class WebsiteBookingConfiguration(TenantOwnedModel):
    """
    Engine rules for public client-facing booking requests.
    """
    website = models.OneToOneField(TenantWebsite, on_delete=models.CASCADE, related_name='booking_config')
    allow_instant_booking = models.BooleanField(default=True)
    require_phone_verification = models.BooleanField(default=False)
    supported_payment_modes = models.JSONField(default=list, blank=True)  # ["COD", "ONLINE", "POST_INVOICE"]
    terms_url = models.CharField(max_length=500, blank=True)
    privacy_url = models.CharField(max_length=500, blank=True)

    def __str__(self):
        return f"Booking Config for {self.website.subdomain}"
