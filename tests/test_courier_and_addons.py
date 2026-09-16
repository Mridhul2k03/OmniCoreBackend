from django.utils import timezone
from decimal import Decimal
from rest_framework.test import APITestCase
from rest_framework import status
from apps.tenants.services import TenantProvisioningService
from apps.subscriptions.models import TenantFeatureOverride
from apps.subscriptions.services import tenant_has_feature, SubscriptionUpgradeService
from apps.courier.models import (
    Hub, CourierAgent, Shipment, ShipmentStatus, ShipmentPickup,
    PickupStatus, Delivery, DeliveryStatus, ProofOfDelivery,
    CourierCommission, CourierPayout, TrackingEvent
)
from apps.courier.services import (
    ShipmentWorkflowService, HubSortingService, ProofOfDeliveryService,
    CourierPayoutService
)
from apps.shuttle.models import (
    ShuttleOrganization, ShuttleRoute, ShuttleStop, PassengerProfile,
    ShuttleTrip, ShuttleTripStatus, AttendanceStatus
)
from apps.shuttle.services import ShuttleOperationService
from apps.warehouse.models import (
    Warehouse, CrossDockOperation, CrossDockStatus,
    ConsolidationGroup, ConsolidationStatus
)
from apps.warehouse.services import CrossDockService, ShipmentConsolidationService
from apps.website.models import TenantWebsite


class CourierAndAddonTests(APITestCase):
    def setUp(self):
        # 1. Provision Tenant A
        self.t_a_data = TenantProvisioningService.provision(
            company_name="Express Logistics A",
            admin_email="admin@express-a.com",
            admin_password="Password123!",
            package_code="CORPORATE"
        )
        self.tenant_a = self.t_a_data['tenant']
        self.user_a = self.t_a_data['admin_user']

        # 2. Provision Tenant B
        self.t_b_data = TenantProvisioningService.provision(
            company_name="Speedy Cargo B",
            admin_email="admin@speedy-b.com",
            admin_password="Password123!",
            package_code="CORPORATE"
        )
        self.tenant_b = self.t_b_data['tenant']
        self.user_b = self.t_b_data['admin_user']

    def test_courier_awb_generation_and_tenant_isolation(self):
        """Authoritative backend AWB generation and strict cross-tenant isolation."""
        self.client.force_authenticate(user=self.user_a)
        
        # Create Shipment for Tenant A
        response = self.client.post('/api/v1/courier/shipments/', {
            'sender_name': 'Alice Sender',
            'sender_phone': '+1234567890',
            'sender_address': '123 Sender St',
            'sender_city': 'New York',
            'sender_postal_code': '10001',
            'receiver_name': 'Bob Receiver',
            'receiver_phone': '+1987654321',
            'delivery_address': '456 Receiver Ave',
            'delivery_city': 'Boston',
            'delivery_postal_code': '02108',
            'service_type': 'EXPRESS',
            'weight_kg': '2.50',
            'parcel_count': 1,
        }, format='json', HTTP_X_TENANT_ID=str(self.tenant_a.id))

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.data.get('data', response.data)
        awb = data['awb_number']
        shipment_id = data['id']
        self.assertTrue(awb.startswith("OCT-AWB-"))

        # Tenant B tries to access Tenant A's shipment -> 404
        self.client.force_authenticate(user=self.user_b)
        res_b = self.client.get(f'/api/v1/courier/shipments/{shipment_id}/', HTTP_X_TENANT_ID=str(self.tenant_b.id))
        self.assertEqual(res_b.status_code, status.HTTP_404_NOT_FOUND)

    def test_multipoint_pickup_and_hub_sorting(self):
        """Multi-point pickup leg execution and hub sorting workflow."""
        hub_origin = Hub.objects.create(tenant=self.tenant_a, name="NYC Central Hub", code="HUB-NYC-01", city="New York")
        hub_dest = Hub.objects.create(tenant=self.tenant_a, name="Boston Sorting Hub", code="HUB-BOS-01", city="Boston")
        
        agent = CourierAgent.objects.create(tenant=self.tenant_a, agent_code="AGT-001", commission_rate_per_delivery=Decimal("15.00"))

        shipment = Shipment.objects.create(
            tenant=self.tenant_a,
            awb_number="OCT-AWB-TEST01",
            sender_name="Sender One",
            sender_phone="+1111",
            sender_address="Addr 1",
            sender_city="NYC",
            sender_postal_code="10001",
            receiver_name="Receiver One",
            receiver_phone="+2222",
            delivery_address="Addr 2",
            delivery_city="BOS",
            delivery_postal_code="02108",
            origin_hub=hub_origin,
            current_hub=hub_origin,
            status=ShipmentStatus.BOOKED
        )

        pickup = ShipmentPickup.objects.create(
            tenant=self.tenant_a,
            shipment=shipment,
            sequence=1,
            address="Addr 1",
            contact_name="Sender One",
            contact_phone="+1111",
            scheduled_time=timezone.now(),
            assigned_agent=agent
        )

        # 1. Assign Pickup
        ShipmentWorkflowService.record_pickup_progress(pickup, "ASSIGN", actor=self.user_a)
        shipment.refresh_from_db()
        self.assertEqual(shipment.status, ShipmentStatus.PICKUP_ASSIGNED)

        # 2. Start Pickup
        ShipmentWorkflowService.record_pickup_progress(pickup, "START", actor=self.user_a)
        shipment.refresh_from_db()
        self.assertEqual(shipment.status, ShipmentStatus.PICKUP_IN_PROGRESS)

        # 2. Complete Pickup
        ShipmentWorkflowService.record_pickup_progress(pickup, "COMPLETE", actor=self.user_a)
        shipment.refresh_from_db()
        self.assertEqual(shipment.status, ShipmentStatus.PICKED_UP)

        # 3. Hub Arrival
        ShipmentWorkflowService.transition_status(shipment, ShipmentStatus.AT_HUB, actor=self.user_a)
        shipment.refresh_from_db()
        self.assertEqual(shipment.status, ShipmentStatus.AT_HUB)

        # 4. Hub Sorting
        record = HubSortingService.process_sorting(
            shipment=shipment,
            source_hub=hub_origin,
            destination_hub=hub_dest,
            operator=self.user_a,
            sorting_category="EXPRESS_NEXT_DAY"
        )
        shipment.refresh_from_db()
        self.assertEqual(shipment.status, ShipmentStatus.SORTED)
        self.assertEqual(shipment.destination_hub, hub_dest)

    def test_delivery_pod_otp_and_payout_workflow(self):
        """Last-mile delivery lifecycle, server OTP generation/verification, and agent payout."""
        agent = CourierAgent.objects.create(
            tenant=self.tenant_a,
            agent_code="AGT-RIDER-7",
            commission_rate_per_delivery=Decimal("25.00")
        )

        shipment = Shipment.objects.create(
            tenant=self.tenant_a,
            awb_number="OCT-AWB-POD-01",
            sender_name="Shipper",
            sender_phone="+100",
            sender_address="St 1",
            sender_city="NYC",
            sender_postal_code="10001",
            receiver_name="John Doe",
            receiver_phone="+200",
            delivery_address="Main St 99",
            delivery_city="NYC",
            delivery_postal_code="10002",
            status=ShipmentStatus.OUT_FOR_DELIVERY
        )

        delivery = Delivery.objects.create(
            tenant=self.tenant_a,
            shipment=shipment,
            agent=agent,
            scheduled_delivery=timezone.now().date(),
            delivery_status=DeliveryStatus.OUT_FOR_DELIVERY,
            delivery_address="Main St 99",
            recipient_name="John Doe",
            recipient_phone="+200"
        )

        # 1. Server generates OTP
        otp = ProofOfDeliveryService.generate_otp_for_delivery(delivery)
        self.assertEqual(len(otp), 6)
        self.assertTrue(otp.isdigit())

        # 2. Invalid OTP rejected
        with self.assertRaises(Exception):
            ProofOfDeliveryService.verify_and_complete_pod(delivery, entered_otp="000000")

        # 3. Valid OTP verified
        pod = ProofOfDeliveryService.verify_and_complete_pod(
            delivery=delivery,
            entered_otp=otp,
            recipient_name="John Doe",
            agent=agent
        )
        self.assertTrue(pod.otp_verified)

        delivery.refresh_from_db()
        shipment.refresh_from_db()
        self.assertEqual(delivery.delivery_status, DeliveryStatus.DELIVERED)
        self.assertEqual(shipment.status, ShipmentStatus.DELIVERED)

        # 4. Agent commission accrued
        commission = CourierCommission.objects.filter(tenant=self.tenant_a, agent=agent, delivery=delivery).first()
        self.assertIsNotNone(commission)
        self.assertEqual(commission.commission_amount, Decimal("25.00"))

        # 5. Payout processing
        today = timezone.now().date()
        payout = CourierPayoutService.process_agent_payout(
            agent=agent,
            period_start=today,
            period_end=today,
            idempotency_key="PAY-TEST-KEY-1",
            actor=self.user_a
        )
        self.assertEqual(payout.net_payable, Decimal("25.00"))
        self.assertEqual(payout.status, "APPROVED")

        # Idempotency check
        duplicate_payout = CourierPayoutService.process_agent_payout(
            agent=agent,
            period_start=today,
            period_end=today,
            idempotency_key="PAY-TEST-KEY-1",
            actor=self.user_a
        )
        self.assertEqual(payout.id, duplicate_payout.id)

    def test_shuttle_operations_workflow(self):
        """School & corporate shuttle route setup, trips, and attendance verification."""
        org = ShuttleOrganization.objects.create(
            tenant=self.tenant_a,
            org_type="CORPORATE",
            name="Tech Park Global",
            code="ORG-TPG",
            contact_person="HR Manager",
            contact_email="hr@tpg.com",
            contact_phone="+9999",
            address="Tech Boulevard 1"
        )

        route = ShuttleRoute.objects.create(
            tenant=self.tenant_a,
            organization=org,
            route_name="Route A - North Campus",
            route_code="SHT-R01",
            start_location="North Metro",
            end_location="Tech Park Campus"
        )

        stop = ShuttleStop.objects.create(
            tenant=self.tenant_a,
            shuttle_route=route,
            stop_name="Station Junction",
            sequence=1
        )

        passenger = PassengerProfile.objects.create(
            tenant=self.tenant_a,
            organization=org,
            first_name="David",
            last_name="Smith",
            id_number="EMP-1044",
            phone="+5555"
        )

        trip = ShuttleTrip.objects.create(
            tenant=self.tenant_a,
            trip_number="TRIP-SHT-001",
            shuttle_route=route,
            trip_date=timezone.now().date(),
            scheduled_start=timezone.now(),
            status=ShuttleTripStatus.SCHEDULED
        )

        # Start trip
        ShuttleOperationService.start_trip(trip, actor=self.user_a)
        trip.refresh_from_db()
        self.assertEqual(trip.status, ShuttleTripStatus.IN_PROGRESS)

        # Record attendance
        attendance = ShuttleOperationService.record_attendance(
            trip=trip,
            passenger=passenger,
            status=AttendanceStatus.BOARDED,
            stop=stop,
            verified_by=self.user_a
        )
        self.assertEqual(attendance.status, AttendanceStatus.BOARDED)

        # Complete trip
        ShuttleOperationService.complete_trip(trip, actor=self.user_a)
        trip.refresh_from_db()
        self.assertEqual(trip.status, ShuttleTripStatus.COMPLETED)

    def test_warehouse_cross_dock_and_consolidation(self):
        """Cross-docking operations and shipment multi-day consolidation."""
        wh = Warehouse.objects.create(tenant=self.tenant_a, name="Apex Logistics Hub", code="WH-APX")

        cd = CrossDockService.start_cross_dock(
            tenant=self.tenant_a,
            warehouse=wh,
            source_loc="Factory Dock 4",
            dest_loc="Regional Dist Center",
            inbound_carrier="LineHaul Logistics",
            operator=self.user_a
        )
        self.assertEqual(cd.status, CrossDockStatus.INBOUND_RECEIVED)

        cd = CrossDockService.advance_status(cd, CrossDockStatus.OUTBOUND_DISPATCHED, outbound_carrier="Express Fleet", actor=self.user_a)
        self.assertEqual(cd.status, CrossDockStatus.OUTBOUND_DISPATCHED)

        # Multi-day Consolidation
        today = timezone.now().date()
        group = ShipmentConsolidationService.create_group(
            tenant=self.tenant_a,
            warehouse=wh,
            destination_zone="Northeast Metro",
            date_from=today,
            date_to=today
        )

        ShipmentConsolidationService.add_item(
            group=group,
            invoice_ref="INV-2026-001",
            parcels=5,
            weight_kg=45.5
        )

        group.refresh_from_db()
        self.assertEqual(group.total_parcels, 5)
        self.assertEqual(group.total_weight_kg, Decimal("45.50"))

    def test_dynamic_website_and_safe_public_tracking(self):
        """Public mini-website config, public booking, and sanitized public tracking."""
        website = TenantWebsite.objects.create(
            tenant=self.tenant_a,
            site_title="Express Delivery Portal",
            subdomain="express-alpha",
            company_name="Express Alpha Ltd",
            contact_email="support@express-alpha.com",
            contact_phone="+123456",
            enabled_verticals=["COURIER"]
        )

        # 1. Public website config
        res_site = self.client.get('/api/v1/public/express-alpha/')
        self.assertEqual(res_site.status_code, status.HTTP_200_OK)
        site_data = res_site.data.get('data', res_site.data)
        self.assertEqual(site_data['site_title'], "Express Delivery Portal")

        # 2. Public courier booking
        res_book = self.client.post('/api/v1/public/express-alpha/courier-booking/', {
            'sender_name': 'Public Shipper',
            'sender_phone': '+1999',
            'sender_address': 'Public Origin 1',
            'sender_city': 'New York',
            'sender_postal_code': '10001',
            'receiver_name': 'Private Recipient',
            'receiver_phone': '+1888',
            'delivery_address': 'Secret House 5',
            'delivery_city': 'Chicago',
            'delivery_postal_code': '60601',
            'weight_kg': '3.0'
        }, format='json')

        self.assertEqual(res_book.status_code, status.HTTP_201_CREATED)
        book_data = res_book.data.get('data', res_book.data)
        awb = book_data['awb_number']

        # 3. Public tracking endpoint strictly sanitizes PII
        res_track = self.client.get(f'/api/v1/public/tracking/{awb}/')
        self.assertEqual(res_track.status_code, status.HTTP_200_OK)
        track_data = res_track.data.get('data', res_track.data)
        self.assertEqual(track_data['awb_number'], awb)
        self.assertEqual(track_data['sender_city'], "New York")
        self.assertEqual(track_data['delivery_city'], "Chicago")
        # Ensure recipient is masked and raw phone / street address / financial details are NOT exposed
        self.assertNotIn("Private Recipient", str(track_data))
        self.assertNotIn("Secret House 5", str(track_data))
        self.assertNotIn("+1888", str(track_data))
        self.assertTrue(track_data['masked_receiver'].startswith("P***"))

    def test_custom_feature_overrides_and_package_upgrades(self):
        """Isolated custom feature provisioning and transactional zero-downtime package upgrades."""
        # 1. Initially tenant does not have 'custom_fleet_ai'
        self.assertFalse(tenant_has_feature(self.tenant_a, 'custom_fleet_ai'))

        # 2. Super admin grants isolated custom feature override
        from apps.subscriptions.models import Feature
        feat, _ = Feature.objects.get_or_create(
            code='custom_fleet_ai',
            defaults={'name': 'Custom Fleet AI'}
        )
        override = TenantFeatureOverride.objects.create(
            tenant=self.tenant_a,
            feature=feat,
            enabled=True,
            reason='Special Pilot Agreement',
            created_by=self.user_a
        )
        self.assertTrue(tenant_has_feature(self.tenant_a, 'custom_fleet_ai'))

        # Override with disable takes precedence
        override.enabled = False
        override.save()
        self.assertFalse(tenant_has_feature(self.tenant_a, 'custom_fleet_ai'))

        # 3. Package Upgrade Workflow
        sub_upgrade = SubscriptionUpgradeService.upgrade(
            tenant=self.tenant_a,
            target_package_code="ENTERPRISE",
            actor=self.user_a
        )
        self.tenant_a.refresh_from_db()
        self.assertEqual(sub_upgrade['subscription'].package.code, "ENTERPRISE")
        self.assertEqual(self.tenant_a.package.code, "ENTERPRISE")


