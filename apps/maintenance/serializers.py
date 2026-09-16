from rest_framework import serializers
from apps.maintenance.models import MaintenanceRecord, MaintenanceSchedule, Breakdown, Accident, RepairOrder


class MaintenanceRecordSerializer(serializers.ModelSerializer):
    vehicle_reg = serializers.CharField(source='vehicle.registration_number', read_only=True)

    class Meta:
        model = MaintenanceRecord
        fields = ['id', 'vehicle', 'vehicle_reg', 'service_type', 'odometer_reading', 'performed_date', 'service_center', 'cost', 'notes', 'created_at']
        read_only_fields = ['id', 'created_at']


class MaintenanceScheduleSerializer(serializers.ModelSerializer):
    vehicle_reg = serializers.CharField(source='vehicle.registration_number', read_only=True)

    class Meta:
        model = MaintenanceSchedule
        fields = ['id', 'vehicle', 'vehicle_reg', 'interval_km', 'interval_days', 'last_service_date', 'last_service_odometer', 'next_due_date', 'next_due_odometer', 'is_active']
        read_only_fields = ['id']


class BreakdownSerializer(serializers.ModelSerializer):
    vehicle_reg = serializers.CharField(source='vehicle.registration_number', read_only=True)
    driver_name = serializers.CharField(source='driver.full_name', read_only=True)

    class Meta:
        model = Breakdown
        fields = ['id', 'vehicle', 'vehicle_reg', 'driver', 'driver_name', 'breakdown_date', 'location', 'description', 'is_resolved', 'resolved_at']
        read_only_fields = ['id']


class AccidentSerializer(serializers.ModelSerializer):
    vehicle_reg = serializers.CharField(source='vehicle.registration_number', read_only=True)
    driver_name = serializers.CharField(source='driver.full_name', read_only=True)

    class Meta:
        model = Accident
        fields = ['id', 'vehicle', 'vehicle_reg', 'driver', 'driver_name', 'accident_date', 'location', 'description', 'estimated_damage_cost', 'insurance_claim_number', 'status']
        read_only_fields = ['id']


class RepairOrderSerializer(serializers.ModelSerializer):
    vehicle_reg = serializers.CharField(source='vehicle.registration_number', read_only=True)

    class Meta:
        model = RepairOrder
        fields = ['id', 'order_number', 'vehicle', 'vehicle_reg', 'issue_summary', 'status', 'labor_cost', 'parts_cost', 'total_cost', 'notes', 'created_at']
        read_only_fields = ['id', 'created_at']
