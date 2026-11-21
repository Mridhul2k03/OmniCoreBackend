from django.urls import path
from apps.accounts.views import (
    CustomTokenObtainPairView,
    CustomTokenRefreshView,
    LogoutView,
    AuthMeView,
    PasswordChangeView,
    PasswordResetRequestView,
    PasswordResetConfirmView,
)
from apps.subscriptions.views import ActivatePlanView

app_name = 'accounts'

urlpatterns = [
    path('login/', CustomTokenObtainPairView.as_view(), name='auth_login'),
    path('refresh/', CustomTokenRefreshView.as_view(), name='auth_refresh'),
    path('token/refresh/', CustomTokenRefreshView.as_view(), name='auth_token_refresh'),
    path('mfa/verify/', MfaVerifyView.as_view(), name='auth_mfa_verify'),
    path('logout/', LogoutView.as_view(), name='auth_logout'),
    path('me/', AuthMeView.as_view(), name='auth_me'),

    # Password Management
    path('password-change/', PasswordChangeView.as_view(), name='password_change'),
    path('password-reset/', PasswordResetRequestView.as_view(), name='password_reset_request'),
    path('password-reset-confirm/', PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
]
