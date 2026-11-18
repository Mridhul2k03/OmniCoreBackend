from rest_framework import serializers
from decimal import Decimal, ROUND_HALF_UP
from apps.finance.models import (
    Invoice,
    InvoiceItem,
    Payment,
    Expense,
    FuelTransaction,
    TollTransaction,
    Collection,
)


class InvoiceItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceItem
        fields = ['id', 'description', 'quantity', 'unit_price', 'total_amount']
        read_only_fields = ['id', 'total_amount']


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = [
            'id', 'payment_number', 'invoice', 'amount', 'payment_date',
            'payment_method', 'reference_number', 'idempotency_key', 'notes', 'created_at'
        ]
        read_only_fields = ['id', 'payment_number', 'created_at']


class InvoiceSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.company_name', read_only=True)
    items = InvoiceItemSerializer(many=True, read_only=True)
    payments = PaymentSerializer(many=True, read_only=True)

    class Meta:
        model = Invoice
        fields = [
            'id', 'invoice_number', 'customer', 'customer_name', 'trip', 'contract',
            'issue_date', 'due_date', 'subtotal', 'tax_amount', 'total_amount',
            'paid_amount', 'balance_due', 'status', 'notes', 'items', 'payments',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'paid_amount', 'balance_due', 'created_at', 'updated_at']

    def create(self, validated_data):
        subtotal = validated_data.get('subtotal', Decimal('0.00'))
        tax_amount = validated_data.get('tax_amount', Decimal('0.00'))
        total_amount = validated_data.get('total_amount')
        if total_amount is None or total_amount == 0:
            total_amount = subtotal + tax_amount
        validated_data['total_amount'] = total_amount
        validated_data['balance_due'] = max(
            Decimal('0.00'),
            total_amount - validated_data.get('paid_amount', Decimal('0.00'))
        )
        return super().create(validated_data)


class ExpenseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Expense
        fields = ['id', 'expense_number', 'category', 'amount', 'expense_date', 'description', 'approved_by', 'created_at']
        read_only_fields = ['id', 'created_at']


class FuelTransactionSerializer(serializers.ModelSerializer):
    vehicle_reg = serializers.CharField(source='vehicle.registration_number', read_only=True)
    driver_name = serializers.CharField(source='driver.full_name', read_only=True)

    class Meta:
        model = FuelTransaction
        fields = [
            'id', 'vehicle', 'vehicle_reg', 'driver', 'driver_name',
            'transaction_date', 'fuel_station', 'fuel_liters', 'rate_per_liter',
            'total_cost', 'odometer_reading'
        ]
        read_only_fields = ['id', 'total_cost']

    def validate(self, attrs):
        liters = attrs.get('fuel_liters')
        rate = attrs.get('rate_per_liter')
        if liters is not None and rate is not None:
            attrs['total_cost'] = (liters * rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        return attrs


class TollTransactionSerializer(serializers.ModelSerializer):
    vehicle_reg = serializers.CharField(source='vehicle.registration_number', read_only=True)

    class Meta:
        model = TollTransaction
        fields = ['id', 'vehicle', 'vehicle_reg', 'toll_plaza', 'tag_id', 'amount', 'transaction_time']
        read_only_fields = ['id']


class CollectionSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.company_name', read_only=True)

    class Meta:
        model = Collection
        fields = ['id', 'customer', 'customer_name', 'amount', 'collection_date', 'payment_mode', 'reference_id', 'created_at']
        read_only_fields = ['id', 'created_at']
