from rest_framework.views import exception_handler
from rest_framework.exceptions import APIException
from rest_framework import status
from rest_framework.response import Response


class OmniCoreAPIException(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_code = 'BAD_REQUEST'
    default_detail = 'A business rule or operational constraint was violated.'

    def __init__(self, detail=None, code=None, status_code=None, fields=None):
        if status_code is not None:
            self.status_code = status_code
        if code is not None:
            self.default_code = code
        self.fields = fields or {}
        super().__init__(detail=detail, code=code)


class TenantIsolationError(OmniCoreAPIException):
    status_code = status.HTTP_404_NOT_FOUND
    default_code = 'TENANT_RESOURCE_NOT_FOUND'
    default_detail = 'The requested resource was not found within your active tenant scope.'


class TenantSuspendedError(OmniCoreAPIException):
    status_code = status.HTTP_403_FORBIDDEN
    default_code = 'TENANT_SUSPENDED'
    default_detail = 'This tenant account is suspended or inactive. Access to protected features is blocked.'


class FeatureNotEntitledError(OmniCoreAPIException):
    status_code = status.HTTP_403_FORBIDDEN
    default_code = 'FEATURE_NOT_ENTITLED'
    default_detail = 'This feature module is not included in your current subscription package or active add-ons.'


class PermissionDeniedError(OmniCoreAPIException):
    status_code = status.HTTP_403_FORBIDDEN
    default_code = 'PERMISSION_DENIED'
    default_detail = 'You do not have the required operational permissions to perform this action.'


class BusinessValidationError(OmniCoreAPIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_code = 'BUSINESS_RULE_VIOLATION'
    default_detail = 'Validation failed against business rules.'


def custom_exception_handler(exc, context):
    """
    Centralized DRF exception handler returning a clean, enterprise standard error format:
    {
        "success": false,
        "error": {
            "code": "ERROR_CODE",
            "message": "Human readable message",
            "fields": { ... }
        }
    }
    """
    response = exception_handler(exc, context)

    if response is not None:
        error_code = getattr(exc, 'default_code', 'ERROR')
        error_message = 'An error occurred.'
        fields = {}

        if isinstance(exc, OmniCoreAPIException):
            error_code = exc.default_code
            error_message = str(exc.detail) if exc.detail else exc.default_detail
            fields = getattr(exc, 'fields', {})
        elif hasattr(response, 'data'):
            if isinstance(response.data, dict):
                if 'detail' in response.data:
                    error_message = str(response.data['detail'])
                    if hasattr(response.data['detail'], 'code'):
                        error_code = str(response.data['detail'].code).upper()
                    fields = {k: v for k, v in response.data.items() if k != 'detail'}
                else:
                    error_message = 'Validation failed for one or more fields.'
                    error_code = 'VALIDATION_ERROR'
                    fields = response.data
            elif isinstance(response.data, list):
                error_message = str(response.data[0]) if response.data else 'Error occurred'
                error_code = 'VALIDATION_ERROR'
                fields = {'non_field_errors': response.data}
            else:
                error_message = str(response.data)

        # Map standard HTTP statuses to informative default error codes
        if response.status_code == 401:
            error_code = 'AUTHENTICATION_REQUIRED'
        elif response.status_code == 403 and error_code == 'ERROR':
            error_code = 'PERMISSION_DENIED'
        elif response.status_code == 404 and error_code == 'ERROR':
            error_code = 'RESOURCE_NOT_FOUND'
        elif response.status_code == 405:
            error_code = 'METHOD_NOT_ALLOWED'
        elif response.status_code == 429:
            error_code = 'THROTTLED'

        response.data = {
            'success': False,
            'error': {
                'code': error_code,
                'message': error_message,
                'fields': fields
            }
        }

    return response
