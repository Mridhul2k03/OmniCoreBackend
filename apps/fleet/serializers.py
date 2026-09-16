from rest_framework import serializers
from apps.fleet.models import Vehicle, VehicleCategory, VehicleDocument, VehicleAssignment


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
    documents = VehicleDocumentSerializer(many=True, read_only=True)

    class Meta:
        model = Vehicle
        fields = [
            'id', 'registration_number', 'category', 'category_name',
            'make', 'model', 'year', 'vin_number', 'status', 'availability',
            'ownership', 'odometer', 'fuel_type', 'payload_capacity_kg',
            'documents', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
