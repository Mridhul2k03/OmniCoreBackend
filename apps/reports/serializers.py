from datetime import timedelta

from rest_framework import serializers


class ReportRequestSerializer(serializers.Serializer):
    category_id = serializers.ChoiceField(choices=(
        'fleet', 'trips', 'maintenance', 'finance', 'cold_chain',
    ))
    start_date = serializers.DateField()
    end_date = serializers.DateField()

    def validate(self, attrs):
        if attrs['end_date'] < attrs['start_date']:
            raise serializers.ValidationError({'end_date': 'End date must be on or after the start date.'})
        if attrs['end_date'] - attrs['start_date'] > timedelta(days=366):
            raise serializers.ValidationError({'end_date': 'Report date range cannot exceed 366 days.'})
        return attrs
