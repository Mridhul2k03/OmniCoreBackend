from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.crm.views import (
    CustomerViewSet,
    LeadViewSet,
    InquiryViewSet,
    QuotationViewSet,
    CommunicationViewSet,
    FollowUpViewSet,
)

router = DefaultRouter()
router.register('leads', LeadViewSet, basename='leads')
router.register('inquiries', InquiryViewSet, basename='inquiries')
router.register('quotations', QuotationViewSet, basename='quotations')
router.register('communications', CommunicationViewSet, basename='communications')
router.register('follow-ups', FollowUpViewSet, basename='follow_ups')
router.register('', CustomerViewSet, basename='customers')

app_name = 'crm'

urlpatterns = [
    path('crm/', include(router.urls)),
]
