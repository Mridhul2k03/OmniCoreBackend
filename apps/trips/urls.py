from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.trips.views import BookingViewSet, RouteViewSet, TripViewSet, TripExpenseViewSet

router = DefaultRouter()
router.register('bookings', BookingViewSet, basename='bookings')
router.register('routes', RouteViewSet, basename='routes')
router.register('expenses', TripExpenseViewSet, basename='trip_expenses')
router.register('', TripViewSet, basename='trips')

app_name = 'trips'

urlpatterns = [
    path('trips/', include(router.urls)),
]
