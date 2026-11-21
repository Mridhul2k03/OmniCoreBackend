from django.urls import path
from apps.accounts.views import (
    CustomTokenObtainPairView,
    CustomTokenRefreshView,
    LogoutView,
    AuthMeView,
    PasswordChangeView,
    PasswordResetRequestView,
    PasswordResetConfirmView,
    RegistrationOTPView,
    RegistrationOTPVerifyView,
)

app_name = 'accounts'

urlpatterns = [
    path('registration/request-otp/', RegistrationOTPView.as_view(), name='registration_request_otp'),
    path('registration/verify-otp/', RegistrationOTPVerifyView.as_view(), name='registration_verify_otp'),
    path('login/', CustomTokenObtainPairView.as_view(), name='auth_login'),
    path('refresh/', CustomTokenRefreshView.as_view(), name='auth_refresh'),
    path('logout/', LogoutView.as_view(), name='auth_logout'),
    path('me/', AuthMeView.as_view(), name='auth_me'),
    path('password-change/', PasswordChangeView.as_view(), name='password_change'),
    path('password-reset/', PasswordResetRequestView.as_view(), name='password_reset_request'),
    path('password-reset-confirm/', PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
]
