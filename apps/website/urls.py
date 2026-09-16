from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.website.views import (
    TenantWebsiteViewSet, WebsitePageViewSet, WebsiteSectionViewSet,
    WebsiteServiceViewSet, WebsiteBlogPostViewSet, WebsiteFAQViewSet,
    WebsiteBookingConfigurationViewSet,
    PublicWebsiteConfigView, PublicCourierBookingView, PublicTaxiBookingView,
    PublicBusBookingView, PublicTransportRequestView, PublicShipmentTrackingView
)

router = DefaultRouter()
router.register(r'site', TenantWebsiteViewSet, basename='website-site')
router.register(r'pages', WebsitePageViewSet, basename='website-page')
router.register(r'sections', WebsiteSectionViewSet, basename='website-section')
router.register(r'services', WebsiteServiceViewSet, basename='website-service')
router.register(r'blog', WebsiteBlogPostViewSet, basename='website-blog')
router.register(r'faqs', WebsiteFAQViewSet, basename='website-faq')
router.register(r'booking-config', WebsiteBookingConfigurationViewSet, basename='website-booking-config')

# Public unauthenticated routes
public_patterns = [
    path('<slug:tenant_slug>/', PublicWebsiteConfigView.as_view(), name='public-website-config'),
    path('<slug:tenant_slug>/courier-booking/', PublicCourierBookingView.as_view(), name='public-courier-booking'),
    path('<slug:tenant_slug>/taxi-booking/', PublicTaxiBookingView.as_view(), name='public-taxi-booking'),
    path('<slug:tenant_slug>/bus-booking/', PublicBusBookingView.as_view(), name='public-bus-booking'),
    path('<slug:tenant_slug>/transport-request/', PublicTransportRequestView.as_view(), name='public-transport-request'),
    path('tracking/<str:tracking_number>/', PublicShipmentTrackingView.as_view(), name='public-shipment-tracking'),
]

urlpatterns = [
    path('website/', include(router.urls)),
    path('public/', include(public_patterns)),
]
