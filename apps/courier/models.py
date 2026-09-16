import uuid
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from apps.core.models import TenantOwnedModel


class ShipmentServiceType(models.TextChoices):
    STANDARD = 'STANDARD', _('Standard Surface Delivery')
    EXPRESS = 'EXPRESS', _('Express Next-Day')
    SAME_DAY = 'SAME_DAY', _('Same-Day Hyperlocal')
    OVERNIGHT = 'OVERNIGHT', _('Overnight Air Express')


class ShipmentStatus(models.TextChoices):
    BOOKED = 'BOOKED', _('Booked')
    PICKUP_ASSIGNED = 'PICKUP_ASSIGNED', _('Pickup Assigned')
    PICKUP_IN_PROGRESS = 'PICKUP_IN_PROGRESS', _('Pickup In Progress')
    PICKED_UP = 'PICKED_UP', _('Picked Up')
    AT_HUB = 'AT_HUB', _('Arrived at Origin Hub')
    SORTING_PENDING = 'SORTING_PENDING', _('Sorting Pending')
    SORTING = 'SORTING', _('In Sorting')
    SORTED = 'SORTED', _('Sorted')
    IN_TRANSIT = 'IN_TRANSIT', _('Line-Haul In Transit')
    DESTINATION_HUB = 'DESTINATION_HUB', _('Arrived at Destination Hub')
    OUT_FOR_DELIVERY = 'OUT_FOR_DELIVERY', _('Out for Delivery')
    DELIVERY_ATTEMPTED = 'DELIVERY_ATTEMPTED', _('Delivery Attempted')
    DELIVERED = 'DELIVERED', _('Delivered')
    DELIVERY_FAILED = 'DELIVERY_FAILED', _('Delivery Failed')
    RETURNED = 'RETURNED', _('Returned to Origin / RTO')
    CANCELLED = 'CANCELLED', _('Cancelled')


class PickupStatus(models.TextChoices):
    PENDING = 'PENDING', _('Pending Assignment')
    ASSIGNED = 'ASSIGNED', _('Assigned to Rider/Driver')
    IN_PROGRESS = 'IN_PROGRESS', _('Rider En Route')
    COMPLETED = 'COMPLETED', _('Pickup Completed')
    FAILED = 'FAILED', _('Pickup Failed')
    RESCHEDULED = 'RESCHEDULED', _('Rescheduled')


class SortingStatus(models.TextChoices):
    RECEIVED = 'RECEIVED', _('Received at Sorting Bay')
    SORTING_PENDING = 'SORTING_PENDING', _('Sorting Pending')
    SORTING = 'SORTING', _('Actively Sorting')
    SORTED = 'SORTED', _('Sorted to Bag / Cage')
    EXCEPTION = 'EXCEPTION', _('Sorting Exception / Misroute')
    DISPATCHED = 'DISPATCHED', _('Dispatched to Line-Haul')


class DeliveryStatus(models.TextChoices):
    PENDING = 'PENDING', _('Pending Run-Sheet')
    ASSIGNED = 'ASSIGNED', _('Assigned to Agent')
    OUT_FOR_DELIVERY = 'OUT_FOR_DELIVERY', _('Out for Delivery')
    ATTEMPTED = 'ATTEMPTED', _('Attempted')
    DELIVERED = 'DELIVERED', _('Successfully Delivered')
    FAILED = 'FAILED', _('Delivery Failed')
    RESCHEDULED = 'RESCHEDULED', _('Rescheduled')
    RETURNED = 'RETURNED', _('Returned to Hub')


class PayoutStatus(models.TextChoices):
    PENDING = 'PENDING', _('Pending Calculation')
    APPROVED = 'APPROVED', _('Approved by Operations/Finance')
    PROCESSING = 'PROCESSING', _('Processing Bank Transfer')
    PAID = 'PAID', _('Settled & Paid')
    REJECTED = 'REJECTED', _('Rejected')


class VerificationMethod(models.TextChoices):
    OTP = 'OTP', _('One-Time Password (OTP)')
    DIGITAL_SIGNATURE = 'DIGITAL_SIGNATURE', _('Digital Touch Signature')
    BOTH = 'BOTH', _('OTP + Digital Signature')


class Hub(TenantOwnedModel):
    """
    Courier parcel processing center, sorting facility, or local distribution hub.
    """
    name = models.CharField(max_length=150)
    code = models.CharField(max_length=50, db_index=True)
    address = models.TextField()
    city = models.CharField(max_length=100, db_index=True)
    state = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=30, db_index=True)
    contact_phone = models.CharField(max_length=30, blank=True)
    contact_email = models.EmailField(blank=True)
    status = models.CharField(max_length=30, default='ACTIVE')
    capacity_sqft = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='managed_hubs'
    )

    class Meta:
        ordering = ['-created_at']
        unique_together = ('tenant', 'code')
        indexes = [
            models.Index(fields=['tenant', 'code']),
            models.Index(fields=['tenant', 'city']),
        ]

    def __str__(self):
        return f"{self.name} ({self.code}) - {self.city}"


class CourierAgent(TenantOwnedModel):
    """
    Field delivery rider or courier agent performing first-mile pickup and last-mile delivery.
    Can be associated directly with a Driver or User record.
    """
    agent_code = models.CharField(max_length=50, db_index=True)
    driver = models.OneToOneField(
        'drivers.Driver',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='courier_profile'
    )
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='courier_agent_profile'
    )
    vehicle = models.ForeignKey(
        'fleet.Vehicle',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='assigned_courier_agents'
    )
    service_area = models.CharField(max_length=150, blank=True)
    status = models.CharField(max_length=30, default='ACTIVE', db_index=True)
    commission_rate_per_delivery = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)
    current_hub = models.ForeignKey(Hub, null=True, blank=True, on_delete=models.SET_NULL, related_name='active_agents')

    class Meta:
        ordering = ['-created_at']
        unique_together = ('tenant', 'agent_code')

    def __str__(self):
        name = self.driver.full_name if self.driver else (self.user.full_name if self.user else self.agent_code)
        return f"Agent {self.agent_code} - {name}"

    @property
    def display_name(self):
        if self.driver:
            return self.driver.full_name
        if self.user:
            return self.user.full_name
        return self.agent_code


class Shipment(TenantOwnedModel):
    """
    Core courier parcel shipment entity with authoritative server-generated AWB.
    """
    awb_number = models.CharField(max_length=50, unique=True, db_index=True, help_text="Authoritative server-generated tracking AWB")
    customer = models.ForeignKey('crm.Customer', null=True, blank=True, on_delete=models.SET_NULL, related_name='courier_shipments')
    invoice = models.ForeignKey('finance.Invoice', null=True, blank=True, on_delete=models.SET_NULL, related_name='courier_shipments')
    
    # Shipper / Sender details
    sender_name = models.CharField(max_length=150)
    sender_phone = models.CharField(max_length=30, db_index=True)
    sender_email = models.EmailField(blank=True)
    sender_address = models.TextField()
    sender_city = models.CharField(max_length=100)
    sender_postal_code = models.CharField(max_length=30)
    
    # Consignee / Receiver details
    receiver_name = models.CharField(max_length=150)
    receiver_phone = models.CharField(max_length=30, db_index=True)
    receiver_email = models.EmailField(blank=True)
    delivery_address = models.TextField()
    delivery_city = models.CharField(max_length=100, db_index=True)
    delivery_postal_code = models.CharField(max_length=30, db_index=True)
    
    # Package specifications
    service_type = models.CharField(max_length=30, choices=ShipmentServiceType.choices, default=ShipmentServiceType.STANDARD)
    weight_kg = models.DecimalField(max_digits=8, decimal_places=2, default=1.00)
    dimensions = models.CharField(max_length=100, blank=True, help_text="LxWxH in cm")
    parcel_count = models.PositiveIntegerField(default=1)
    declared_value = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    # Hub routing & agent allocation
    origin_hub = models.ForeignKey(Hub, null=True, blank=True, on_delete=models.SET_NULL, related_name='originating_shipments')
    current_hub = models.ForeignKey(Hub, null=True, blank=True, on_delete=models.SET_NULL, related_name='current_shipments')
    destination_hub = models.ForeignKey(Hub, null=True, blank=True, on_delete=models.SET_NULL, related_name='destination_shipments')
    assigned_agent = models.ForeignKey(CourierAgent, null=True, blank=True, on_delete=models.SET_NULL, related_name='assigned_shipments')
    
    # Lifecycle
    status = models.CharField(
        max_length=40,
        choices=ShipmentStatus.choices,
        default=ShipmentStatus.BOOKED,
        db_index=True
    )
    expected_delivery = models.DateTimeField(null=True, blank=True, db_index=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', 'status']),
            models.Index(fields=['tenant', 'awb_number']),
            models.Index(fields=['tenant', 'delivery_postal_code']),
            models.Index(fields=['tenant', 'created_at']),
        ]

    def __str__(self):
        return f"AWB {self.awb_number} ({self.sender_city} -> {self.delivery_city}) [{self.status}]"


class ShipmentParcel(TenantOwnedModel):
    """
    Sub-parcels for multi-box / consolidated shipments.
    """
    shipment = models.ForeignKey(Shipment, on_delete=models.CASCADE, related_name='parcels')
    barcode = models.CharField(max_length=100, db_index=True)
    weight_kg = models.DecimalField(max_digits=8, decimal_places=2)
    dimensions = models.CharField(max_length=100, blank=True)
    description = models.CharField(max_length=255, blank=True)


class PickupLocation(TenantOwnedModel):
    """
    Predefined or recurring pickup address location.
    """
    name = models.CharField(max_length=150)
    contact_person = models.CharField(max_length=150)
    contact_phone = models.CharField(max_length=30)
    address = models.TextField()
    city = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=30)
    notes = models.TextField(blank=True)


class ShipmentPickup(TenantOwnedModel):
    """
    Multi-point pickup leg supporting complex work orders.
    """
    shipment = models.ForeignKey(Shipment, on_delete=models.CASCADE, related_name='pickups')
    pickup_location = models.ForeignKey(PickupLocation, null=True, blank=True, on_delete=models.SET_NULL)
    sequence = models.PositiveIntegerField(default=1)
    address = models.TextField()
    contact_name = models.CharField(max_length=150)
    contact_phone = models.CharField(max_length=30)
    scheduled_time = models.DateTimeField(db_index=True)
    assigned_agent = models.ForeignKey(CourierAgent, null=True, blank=True, on_delete=models.SET_NULL, related_name='assigned_pickups')
    status = models.CharField(max_length=30, choices=PickupStatus.choices, default=PickupStatus.PENDING)
    actual_pickup_time = models.DateTimeField(null=True, blank=True)
    failure_reason = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['sequence']
        indexes = [
            models.Index(fields=['tenant', 'status']),
            models.Index(fields=['tenant', 'scheduled_time']),
        ]


class HubShipment(TenantOwnedModel):
    """
    Movement and dwell-time log of a shipment inside a hub facility.
    """
    hub = models.ForeignKey(Hub, on_delete=models.CASCADE, related_name='hub_shipments')
    shipment = models.ForeignKey(Shipment, on_delete=models.CASCADE, related_name='hub_movements')
    arrival_time = models.DateTimeField(auto_now_add=True)
    departure_time = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=30, default='RECEIVED')  # RECEIVED, STORED, DISPATCHED

    class Meta:
        indexes = [
            models.Index(fields=['tenant', 'hub', 'status']),
        ]


class SortingRecord(TenantOwnedModel):
    """
    Audit log of sorting operations performed at a hub.
    """
    shipment = models.ForeignKey(Shipment, on_delete=models.CASCADE, related_name='sorting_records')
    source_hub = models.ForeignKey(Hub, on_delete=models.CASCADE, related_name='outbound_sortings')
    destination_hub = models.ForeignKey(Hub, null=True, blank=True, on_delete=models.SET_NULL, related_name='inbound_sortings')
    sorting_category = models.CharField(max_length=100, default='STANDARD')
    operator = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    status = models.CharField(max_length=30, choices=SortingStatus.choices, default=SortingStatus.RECEIVED)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    notes = models.TextField(blank=True)


class TrackingEvent(TenantOwnedModel):
    """
    Authoritative milestone tracking event for first-mile, line-haul, and last-mile visibility.
    """
    shipment = models.ForeignKey(Shipment, on_delete=models.CASCADE, related_name='tracking_events')
    event_type = models.CharField(max_length=100, db_index=True)
    status = models.CharField(max_length=40)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    location = models.CharField(max_length=150, blank=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    description = models.CharField(max_length=255)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['timestamp']
        indexes = [
            models.Index(fields=['tenant', 'shipment', 'timestamp']),
        ]

    def __str__(self):
        return f"[{self.timestamp.strftime('%Y-%m-%d %H:%M')}] AWB {self.shipment.awb_number} -> {self.event_type}"


class Delivery(TenantOwnedModel):
    """
    Last-mile delivery execution task.
    """
    shipment = models.OneToOneField(Shipment, on_delete=models.CASCADE, related_name='delivery_task')
    invoice = models.ForeignKey('finance.Invoice', null=True, blank=True, on_delete=models.SET_NULL)
    agent = models.ForeignKey(CourierAgent, null=True, blank=True, on_delete=models.SET_NULL, related_name='deliveries')
    scheduled_delivery = models.DateField(db_index=True)
    delivery_status = models.CharField(max_length=30, choices=DeliveryStatus.choices, default=DeliveryStatus.PENDING, db_index=True)
    attempt_count = models.PositiveIntegerField(default=0)
    delivery_address = models.TextField()
    recipient_name = models.CharField(max_length=150)
    recipient_phone = models.CharField(max_length=30)
    notes = models.TextField(blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['tenant', 'delivery_status']),
            models.Index(fields=['tenant', 'scheduled_delivery']),
        ]


class DeliveryAttempt(TenantOwnedModel):
    """
    Timestamped attempt history for last-mile deliveries.
    """
    delivery = models.ForeignKey(Delivery, on_delete=models.CASCADE, related_name='attempts')
    attempt_number = models.PositiveIntegerField()
    timestamp = models.DateTimeField(auto_now_add=True)
    reason = models.CharField(max_length=100)  # CONSIGNEE_UNAVAILABLE, INCORRECT_ADDRESS, CUSTOMER_REFUSED
    notes = models.TextField(blank=True)


class ProofOfDelivery(TenantOwnedModel):
    """
    Tamper-proof Proof of Delivery (PoD) with server-side OTP and digital signature.
    """
    delivery = models.OneToOneField(Delivery, on_delete=models.CASCADE, related_name='pod')
    verification_method = models.CharField(max_length=30, choices=VerificationMethod.choices, default=VerificationMethod.OTP)
    otp_code = models.CharField(max_length=10, blank=True, help_text="Server-generated authoritative delivery OTP")
    otp_verified = models.BooleanField(default=False)
    digital_signature_file = models.CharField(max_length=500, blank=True, help_text="S3 tenant-scoped signature file path")
    recipient_name = models.CharField(max_length=150)
    delivery_timestamp = models.DateTimeField(null=True, blank=True)
    agent = models.ForeignKey(CourierAgent, null=True, blank=True, on_delete=models.SET_NULL)
    notes = models.TextField(blank=True)
    attachment_file = models.CharField(max_length=500, blank=True)

    def __str__(self):
        return f"PoD for Delivery {self.delivery.id} ({self.recipient_name})"


class CourierCommission(TenantOwnedModel):
    """
    Itemized earnings ledger for courier agents.
    """
    agent = models.ForeignKey(CourierAgent, on_delete=models.CASCADE, related_name='commissions')
    delivery = models.ForeignKey(Delivery, null=True, blank=True, on_delete=models.SET_NULL)
    shipment = models.ForeignKey(Shipment, null=True, blank=True, on_delete=models.SET_NULL)
    commission_amount = models.DecimalField(max_digits=10, decimal_places=2)
    date = models.DateField(auto_now_add=True, db_index=True)
    status = models.CharField(max_length=30, default='EARNED')  # EARNED, SETTLED, CANCELLED


class CourierExpense(TenantOwnedModel):
    """
    On-road expenses incurred by courier agents (fuel, toll, parking).
    """
    agent = models.ForeignKey(CourierAgent, on_delete=models.CASCADE, related_name='expenses')
    expense_type = models.CharField(max_length=50, default='FUEL')  # FUEL, PARKING, PHONE, MAINTENANCE
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    date = models.DateField(auto_now_add=True)
    notes = models.TextField(blank=True)
    is_approved = models.BooleanField(default=False)


class CourierPayout(TenantOwnedModel):
    """
    Auditable payout run aggregating earnings minus deductions.
    Protected with idempotency mechanisms.
    """
    payout_number = models.CharField(max_length=100, db_index=True)
    agent = models.ForeignKey(CourierAgent, on_delete=models.CASCADE, related_name='payouts')
    gross_amount = models.DecimalField(max_digits=12, decimal_places=2)
    total_deductions = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    net_payable = models.DecimalField(max_digits=12, decimal_places=2)
    period_start = models.DateField()
    period_end = models.DateField()
    status = models.CharField(max_length=30, choices=PayoutStatus.choices, default=PayoutStatus.PENDING, db_index=True)
    idempotency_key = models.CharField(max_length=128, blank=True, null=True, db_index=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        unique_together = ('tenant', 'idempotency_key')
        indexes = [
            models.Index(fields=['tenant', 'status']),
            models.Index(fields=['tenant', 'agent']),
        ]

    def __str__(self):
        return f"Payout {self.payout_number} -> {self.agent.display_name} (${self.net_payable}) [{self.status}]"
