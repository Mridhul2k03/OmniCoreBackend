from django.urls import path
from apps.accounts.views import (
    CustomTokenObtainPairView,
    CustomTokenRefreshView,
    LogoutView,
    AuthMeView,
    PasswordChangeView,
    PasswordResetRequestView,
    PasswordResetConfirmView,
    RegisterView,
    MfaVerifyView,
)
from apps.subscriptions.views import ActivatePlanView

app_name = 'accounts'

urlpatterns = [
    # Registration & Onboarding
    path('register/', RegisterView.as_view(), name='auth_register'),
    path('signup/', RegisterView.as_view(), name='auth_signup'),
    path('activate-plan/', ActivatePlanView.as_view(), name='auth_activate_plan'),

    # Authentication
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
