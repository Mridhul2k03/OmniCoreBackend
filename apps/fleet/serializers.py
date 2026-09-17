from rest_framework import serializers
from apps.fleet.models import (
    Vehicle,
    VehicleCategory,
    VehicleDocument,
    VehicleAssignment,
    Branch,
)


class BranchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Branch
        fields = [
            'id', 'name', 'code', 'city', 'state', 'address',
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class VehicleCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = VehicleCategory
        fields = ['id', 'name', 'code', 'description', 'created_at']
        read_only_fields = ['id', 'created_at']


class VehicleDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = VehicleDocument
        fields = [
            'id', 'vehicle', 'document_type', 'document_number',
            'issue_date', 'expiry_date', 'file_path', 'status', 'notes', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class VehicleAssignmentSerializer(serializers.ModelSerializer):
    driver_name = serializers.CharField(source='driver.full_name', read_only=True)

    class Meta:
        model = VehicleAssignment
        fields = ['id', 'vehicle', 'driver', 'driver_name', 'assigned_from', 'assigned_to', 'is_active', 'notes']
        read_only_fields = ['id']


class VehicleSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    branch_name = serializers.CharField(source='branch.name', read_only=True)
    assigned_driver_name = serializers.CharField(source='assigned_driver.full_name', read_only=True)
    documents = VehicleDocumentSerializer(many=True, read_only=True)

    # Legacy aliases (write-only so they don't conflict with model properties on serialization)
    vin_number = serializers.CharField(source='vin', required=False, write_only=True)
    odometer = serializers.DecimalField(source='odometer_km', max_digits=12, decimal_places=2, required=False, write_only=True)
    payload_capacity_kg = serializers.DecimalField(source='capacity_kg', max_digits=10, decimal_places=2, required=False, write_only=True)

    class Meta:
        model = Vehicle
        fields = [
            'id', 'registration_number', 'category', 'category_name',
            'branch', 'branch_name', 'assigned_driver', 'assigned_driver_name',
            'vertical', 'type', 'make', 'model', 'year',
            'vin', 'vin_number', 'status', 'availability', 'ownership',
            'odometer_km', 'odometer', 'fuel_type', 'capacity_kg', 'payload_capacity_kg',
            'temperature_sensor', 'fuel_level_percent', 'engine_oil_life_percent', 'ad_blue_level_percent',
            'documents', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def to_internal_value(self, data):
        data = data.copy() if hasattr(data, 'copy') else dict(data)
        # Map input aliases if primary name not provided
        if 'vin_number' in data and 'vin' not in data:
            data['vin'] = data['vin_number']
        if 'odometer' in data and 'odometer_km' not in data:
            data['odometer_km'] = data['odometer']
        if 'payload_capacity_kg' in data and 'capacity_kg' not in data:
            data['capacity_kg'] = data['payload_capacity_kg']
        return super().to_internal_value(data)

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        # Ensure backward-compatible aliases are present in responses
        ret['vin_number'] = ret.get('vin')
        ret['odometer'] = ret.get('odometer_km')
        ret['payload_capacity_kg'] = ret.get('capacity_kg')
        return ret

    def validate(self, attrs):
        instance = getattr(self, 'instance', None)
        if instance and instance.pk:
            if 'assigned_driver' in attrs:
                new_driver = attrs['assigned_driver']
                if new_driver != instance.assigned_driver:
                    current_status = str(instance.status).lower()
                    target_status = str(attrs.get('status', instance.status)).lower()
                    if current_status == 'on_trip' or target_status == 'on_trip':
                        raise serializers.ValidationError({
                            'assigned_driver': "Cannot reassign driver while vehicle status is 'on_trip'."
                        })
        return attrs
