from rest_framework_simplejwt.authentication import JWTAuthentication
from django.conf import settings


class CookieJWTAuthentication(JWTAuthentication):
    """
    Extends SimpleJWT's JWTAuthentication to read tokens from either:
    1. 'Authorization: Bearer <token>' header (API clients / Mobile / curl)
    2. 'access_token' HTTP-only cookie (Web applications with cookie-based auth)
    """

    def authenticate(self, request):
        header = self.get_header(request)
        if header is None:
            # Fallback to reading the access token from request cookies
            raw_token = (
                request.COOKIES.get('access_token')
                or request.COOKIES.get('jwt_access')
            )
        else:
            raw_token = self.get_raw_token(header)

        if raw_token is None:
            return None

        validated_token = self.get_validated_token(raw_token)
        return self.get_user(validated_token), validated_token
