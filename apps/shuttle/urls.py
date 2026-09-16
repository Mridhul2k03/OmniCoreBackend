from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.shuttle.views import (
    ShuttleOrganizationViewSet, ShuttleRouteViewSet, ShuttleStopViewSet,
    ShuttleScheduleViewSet, PassengerProfileViewSet, ShuttleAssignmentViewSet,
    ShuttleAttendanceViewSet, ShuttleTripViewSet
)

router = DefaultRouter()
router.register(r'organizations', ShuttleOrganizationViewSet, basename='shuttle-organization')
router.register(r'routes', ShuttleRouteViewSet, basename='shuttle-route')
router.register(r'stops', ShuttleStopViewSet, basename='shuttle-stop')
router.register(r'schedules', ShuttleScheduleViewSet, basename='shuttle-schedule')
router.register(r'passengers', PassengerProfileViewSet, basename='shuttle-passenger')
router.register(r'assignments', ShuttleAssignmentViewSet, basename='shuttle-assignment')
router.register(r'attendance', ShuttleAttendanceViewSet, basename='shuttle-attendance')
router.register(r'trips', ShuttleTripViewSet, basename='shuttle-trip')

urlpatterns = [
    path('', include(router.urls)),
]
