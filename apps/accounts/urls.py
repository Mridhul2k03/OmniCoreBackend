from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from apps.accounts.views import (
    CustomTokenObtainPairView,
    LogoutView,
    AuthMeView,
    PasswordChangeView,
    PasswordResetRequestView,
    PasswordResetConfirmView,
)

app_name = 'accounts'

urlpatterns = [
    path('login/', CustomTokenObtainPairView.as_view(), name='auth_login'),
    path('refresh/', TokenRefreshView.as_view(), name='auth_refresh'),
    path('logout/', LogoutView.as_view(), name='auth_logout'),
    path('me/', AuthMeView.as_view(), name='auth_me'),
    path('password-change/', PasswordChangeView.as_view(), name='password_change'),
    path('password-reset/', PasswordResetRequestView.as_view(), name='password_reset_request'),
    path('password-reset-confirm/', PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
]
