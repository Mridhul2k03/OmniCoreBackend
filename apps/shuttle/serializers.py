from rest_framework import serializers
from apps.shuttle.models import (
    ShuttleOrganization, ShuttleRoute, ShuttleStop, ShuttleSchedule,
    PassengerProfile, ShuttleAssignment, ShuttleTrip, ShuttleAttendance
)


class ShuttleOrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShuttleOrganization
        fields = [
            'id', 'org_type', 'name', 'code', 'contact_person', 'contact_email',
            'contact_phone', 'address', 'configuration', 'is_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class ShuttleStopSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShuttleStop
        fields = [
            'id', 'shuttle_route', 'stop_name', 'sequence', 'landmark',
            'latitude', 'longitude', 'scheduled_offset_minutes'
        ]
        read_only_fields = ['id']


class ShuttleRouteSerializer(serializers.ModelSerializer):
    stops = ShuttleStopSerializer(many=True, read_only=True)
    organization_name = serializers.ReadOnlyField(source='organization.name')

    class Meta:
        model = ShuttleRoute
        fields = [
            'id', 'organization', 'organization_name', 'base_route',
            'route_name', 'route_code', 'direction', 'start_location',
            'end_location', 'default_vehicle', 'default_driver',
            'is_active', 'stops', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'organization_name', 'created_at', 'updated_at']


class ShuttleScheduleSerializer(serializers.ModelSerializer):
    route_code = serializers.ReadOnlyField(source='shuttle_route.route_code')

    class Meta:
        model = ShuttleSchedule
        fields = [
            'id', 'shuttle_route', 'route_code', 'day_of_week',
            'departure_time', 'estimated_arrival_time', 'vehicle',
            'driver', 'is_active'
        ]
        read_only_fields = ['id', 'route_code']


class PassengerProfileSerializer(serializers.ModelSerializer):
    organization_name = serializers.ReadOnlyField(source='organization.name')

    class Meta:
        model = PassengerProfile
        fields = [
            'id', 'organization', 'organization_name', 'passenger_type',
            'first_name', 'last_name', 'id_number', 'email', 'phone',
            'pickup_stop', 'dropoff_stop', 'emergency_contact_name',
            'emergency_contact_phone', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'organization_name', 'created_at', 'updated_at']


class ShuttleAssignmentSerializer(serializers.ModelSerializer):
    passenger_name = serializers.SerializerMethodField()
    route_code = serializers.ReadOnlyField(source='shuttle_route.route_code')

    class Meta:
        model = ShuttleAssignment
        fields = [
            'id', 'passenger', 'passenger_name', 'shuttle_route', 'route_code',
            'seat_number', 'effective_from', 'effective_to', 'is_active', 'created_at'
        ]
        read_only_fields = ['id', 'passenger_name', 'route_code', 'created_at']

    def get_passenger_name(self, obj):
        return f"{obj.passenger.first_name} {obj.passenger.last_name}"


class ShuttleAttendanceSerializer(serializers.ModelSerializer):
    passenger_name = serializers.SerializerMethodField()

    class Meta:
        model = ShuttleAttendance
        fields = [
            'id', 'shuttle_trip', 'passenger', 'passenger_name',
            'shuttle_stop', 'status', 'timestamp', 'verified_by', 'notes'
        ]
        read_only_fields = ['id', 'passenger_name', 'timestamp']

    def get_passenger_name(self, obj):
        return f"{obj.passenger.first_name} {obj.passenger.last_name}"


class ShuttleTripSerializer(serializers.ModelSerializer):
    attendance_records = ShuttleAttendanceSerializer(many=True, read_only=True)
    route_code = serializers.ReadOnlyField(source='shuttle_route.route_code')

    class Meta:
        model = ShuttleTrip
        fields = [
            'id', 'trip_number', 'shuttle_route', 'route_code', 'schedule',
            'vehicle', 'driver', 'trip_date', 'scheduled_start', 'actual_start',
            'actual_end', 'status', 'notes', 'attendance_records', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'route_code', 'created_at', 'updated_at']
