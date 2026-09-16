from rest_framework import serializers
from apps.drivers.models import Driver, DriverDocument, DriverAssignment, Attendance, DriverIncident


class DriverDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = DriverDocument
        fields = ['id', 'driver', 'document_type', 'document_number', 'issue_date', 'expiry_date', 'file_path', 'is_verified', 'created_at']
        read_only_fields = ['id', 'created_at']


class DriverIncidentSerializer(serializers.ModelSerializer):
    class Meta:
        model = DriverIncident
        fields = ['id', 'driver', 'vehicle', 'incident_date', 'severity', 'location', 'description', 'action_taken', 'fine_amount', 'created_at']
        read_only_fields = ['id', 'created_at']


class AttendanceSerializer(serializers.ModelSerializer):
    driver_name = serializers.CharField(source='driver.full_name', read_only=True)

    class Meta:
        model = Attendance
        fields = ['id', 'driver', 'driver_name', 'date', 'check_in_time', 'check_out_time', 'status', 'notes']
        read_only_fields = ['id']


class DriverSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    documents = DriverDocumentSerializer(many=True, read_only=True)
    incidents = DriverIncidentSerializer(many=True, read_only=True)
    current_vehicle_reg = serializers.CharField(source='current_vehicle.registration_number', read_only=True)

    class Meta:
        model = Driver
        fields = [
            'id', 'first_name', 'last_name', 'full_name', 'phone', 'email',
            'license_number', 'license_type', 'license_expiry', 'status',
            'current_vehicle', 'current_vehicle_reg', 'emergency_contact_name',
            'emergency_contact_phone', 'date_of_joining', 'notes',
            'documents', 'incidents', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
