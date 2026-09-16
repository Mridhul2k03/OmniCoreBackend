from rest_framework import serializers
from apps.website.models import (
    TenantWebsite, WebsitePage, WebsiteSection, WebsiteService,
    WebsiteBlogPost, WebsiteFAQ, WebsiteBookingConfiguration
)


class WebsiteSectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = WebsiteSection
        fields = ['id', 'page', 'section_type', 'heading', 'subheading', 'content', 'sequence']
        read_only_fields = ['id']


class WebsitePageSerializer(serializers.ModelSerializer):
    sections = WebsiteSectionSerializer(many=True, read_only=True)

    class Meta:
        model = WebsitePage
        fields = ['id', 'website', 'title', 'slug', 'meta_description', 'is_published', 'order', 'sections']
        read_only_fields = ['id']


class WebsiteServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = WebsiteService
        fields = ['id', 'website', 'vertical', 'title', 'description', 'icon', 'pricing_summary', 'is_featured']
        read_only_fields = ['id']


class WebsiteBlogPostSerializer(serializers.ModelSerializer):
    class Meta:
        model = WebsiteBlogPost
        fields = ['id', 'website', 'title', 'slug', 'content', 'author_name', 'published_at', 'is_published']
        read_only_fields = ['id']


class WebsiteFAQSerializer(serializers.ModelSerializer):
    class Meta:
        model = WebsiteFAQ
        fields = ['id', 'website', 'question', 'answer', 'category', 'sequence']
        read_only_fields = ['id']


class WebsiteBookingConfigurationSerializer(serializers.ModelSerializer):
    class Meta:
        model = WebsiteBookingConfiguration
        fields = ['id', 'website', 'allow_instant_booking', 'require_phone_verification', 'supported_payment_modes', 'terms_url', 'privacy_url']
        read_only_fields = ['id']


class TenantWebsiteSerializer(serializers.ModelSerializer):
    pages = WebsitePageSerializer(many=True, read_only=True)
    services = WebsiteServiceSerializer(many=True, read_only=True)
    booking_config = WebsiteBookingConfigurationSerializer(read_only=True)

    class Meta:
        model = TenantWebsite
        fields = [
            'id', 'site_title', 'subdomain', 'custom_domain', 'logo_url', 'favicon_url',
            'company_name', 'tagline', 'about_text', 'contact_email', 'contact_phone',
            'address', 'theme', 'social_links', 'enabled_verticals', 'is_published',
            'pages', 'services', 'booking_config', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


# Public safe booking input serializers
class PublicCourierBookingSerializer(serializers.Serializer):
    sender_name = serializers.CharField(max_length=150)
    sender_phone = serializers.CharField(max_length=30)
    sender_address = serializers.CharField()
    sender_city = serializers.CharField(max_length=100)
    sender_postal_code = serializers.CharField(max_length=30)
    receiver_name = serializers.CharField(max_length=150)
    receiver_phone = serializers.CharField(max_length=30)
    delivery_address = serializers.CharField()
    delivery_city = serializers.CharField(max_length=100)
    delivery_postal_code = serializers.CharField(max_length=30)
    service_type = serializers.CharField(default='STANDARD')
    weight_kg = serializers.DecimalField(max_digits=8, decimal_places=2, default=1.0)
    declared_value = serializers.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    notes = serializers.CharField(required=False, allow_blank=True)


class PublicTaxiBookingSerializer(serializers.Serializer):
    passenger_name = serializers.CharField(max_length=150)
    passenger_phone = serializers.CharField(max_length=30)
    pickup_address = serializers.CharField()
    dropoff_address = serializers.CharField()
    pickup_time = serializers.DateTimeField()
    vehicle_type = serializers.CharField(default='SEDAN')
    passenger_count = serializers.IntegerField(default=1)
    notes = serializers.CharField(required=False, allow_blank=True)


class PublicBusBookingSerializer(serializers.Serializer):
    passenger_name = serializers.CharField(max_length=150)
    passenger_phone = serializers.CharField(max_length=30)
    passenger_email = serializers.EmailField(required=False, allow_blank=True)
    trip_id = serializers.CharField()
    seat_numbers = serializers.ListField(child=serializers.CharField(), allow_empty=False)
    boarding_point = serializers.CharField()
    dropping_point = serializers.CharField()


class PublicTransportRequestSerializer(serializers.Serializer):
    shipper_name = serializers.CharField(max_length=150)
    shipper_phone = serializers.CharField(max_length=30)
    shipper_email = serializers.EmailField(required=False, allow_blank=True)
    origin = serializers.CharField()
    destination = serializers.CharField()
    cargo_type = serializers.CharField()
    weight_tons = serializers.DecimalField(max_digits=8, decimal_places=2)
    requested_date = serializers.DateField()
    notes = serializers.CharField(required=False, allow_blank=True)
