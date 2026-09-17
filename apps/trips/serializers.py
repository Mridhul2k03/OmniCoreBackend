from rest_framework import serializers
from apps.trips.models import Booking, Route, Trip, TripExpense


class RouteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Route
        fields = ['id', 'name', 'origin', 'destination', 'standard_distance_km', 'estimated_hours', 'toll_points_count', 'created_at']
        read_only_fields = ['id', 'created_at']


class BookingSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.company_name', read_only=True)

    class Meta:
        model = Booking
        fields = [
            'id', 'booking_number', 'customer', 'customer_name', 'pickup_location',
            'dropoff_location', 'cargo_type', 'cargo_weight_kg', 'scheduled_date',
            'commercial_rate', 'status', 'notes', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class TripExpenseSerializer(serializers.ModelSerializer):
    class Meta:
        model = TripExpense
        fields = ['id', 'trip', 'expense_type', 'amount', 'receipt_number', 'receipt_file', 'notes', 'is_approved', 'created_at']
        read_only_fields = ['id', 'created_at']


class TripSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.company_name', read_only=True)
    vehicle_reg = serializers.CharField(source='vehicle.registration_number', read_only=True)
    driver_name = serializers.CharField(source='driver.full_name', read_only=True)
    expenses = TripExpenseSerializer(many=True, read_only=True)

    class Meta:
        model = Trip
        fields = [
            'id', 'trip_number', 'customer', 'customer_name', 'booking', 'vehicle',
            'vehicle_reg', 'driver', 'driver_name', 'route', 'origin', 'destination',
            'scheduled_start', 'scheduled_end', 'actual_start', 'actual_end',
            'start_odometer', 'end_odometer', 'distance_km', 'freight_charge',
            'advance_paid', 'detention_charges', 'status', 'notes', 'expenses',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

