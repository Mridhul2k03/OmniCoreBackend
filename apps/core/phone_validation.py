import re

from rest_framework import serializers


class PhoneNumberValidationMixin:
    """Normalize local 10-digit or E.164 phone inputs in API serializers."""

    def to_internal_value(self, data):
        attrs = super().to_internal_value(data)
        errors = {}

        for field_name, value in attrs.items():
            if field_name != 'phone' and not field_name.endswith('_phone'):
                continue
            if value in (None, ''):
                continue

            raw_value = str(value).strip()
            digits = re.sub(r'\D', '', raw_value)
            if raw_value.startswith('+'):
                if not re.fullmatch(r'[1-9]\d{10,14}', digits):
                    errors[field_name] = 'Enter a valid international number with a country code.'
                    continue
                attrs[field_name] = f'+{digits}'
            elif re.fullmatch(r'\d{10}', digits):
                # Keep accepting the established API contract for legacy clients;
                # the shared frontend input submits E.164 with its selected prefix.
                attrs[field_name] = digits
            else:
                errors[field_name] = 'Enter exactly 10 local digits, or a number with a + country code.'

        if errors:
            raise serializers.ValidationError(errors)
        return attrs
