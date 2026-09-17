import os
import django
from datetime import date, timedelta
from decimal import Decimal

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.utils import timezone
from apps.tenants.models import Tenant, Vertical
from apps.fleet.models import (
    Branch,
    VehicleCategory,
    Vehicle,
    VehicleDocument,
    VehicleAssignment,
    VehicleStatus,
    VehicleAvailability,
    VehicleOwnership,
    VehicleVertical,
    VehicleType,
    DocumentType,
    DocumentStatus,
)
from apps.drivers.models import Driver, DriverDocument, DriverStatus
from apps.crm.models import Customer, CustomerType
from apps.trips.models import Route, Booking, Trip, TripExpense, BookingStatus, TripStatus, TripExpenseType
from apps.warehouse.models import Warehouse, Supplier, SparePart
from apps.maintenance.models import MaintenanceSchedule, MaintenanceRecord, ServiceType
from apps.insurance.models import InsurancePolicy, PolicyType
from apps.contracts.models import Contract, ContractStatus


def seed_data():
    print("\n=======================================================")
    print("      OMNICORE PLATFORM COMPREHENSIVE DATA SEEDER      ")
    print("=======================================================\n")

    # 1. Tenant
    tenant = Tenant.objects.first()
    if not tenant:
        tenant = Tenant.objects.create(
            tenant_id='OCT-100001',
            company_name='Apex Global Logistics & Cold Chain',
            slug='apex-global',
            status='ACTIVE',
            email='ops@apexlogistics.com',
            phone='+1-312-555-0199',
            address='1000 S Riverside Plaza, Suite 1400, Chicago, IL 60606',
        )
    print(f"[+] Using Tenant: {tenant.company_name} (ID: {tenant.tenant_id})")

    # 2. Verticals
    vertical_data = [
        ('cold_chain', 'Cold Chain & Temperature Controlled'),
        ('freight_logistics', 'Freight Logistics & Line-Haul'),
        ('b2b_contract', 'B2B Dedicated Fleet Contract'),
        ('last_mile', 'Urban Last-Mile Delivery'),
        ('courier_express', 'Courier & Parcel Express'),
        ('corporate_shuttle', 'Corporate & Employee Shuttle'),
        ('heavy_machinery', 'Heavy Haulage & Industrial Equipment'),
        ('tourist_bus', 'Intercity Coach & Tourist Bus'),
        ('taxi_cab', 'On-Demand Urban Taxi'),
        ('packers_movers', 'Packers, Movers & Relocation'),
    ]
    vertical_objs = []
    for code, name in vertical_data:
        v, _ = Vertical.objects.get_or_create(code=code, defaults={'name': name, 'is_active': True})
        vertical_objs.append(v)
    tenant.verticals.set(vertical_objs)
    print(f"[+] Seeded {len(vertical_objs)} Industry Verticals")

    # 3. Branches
    branch_specs = [
        ('Chicago Central Depot', 'CHI-01', 'Chicago', 'IL', '4200 W 47th St, Chicago, IL 60632'),
        ('Dallas-Fort Worth Linehaul Hub', 'DFW-02', 'Dallas', 'TX', '2400 Aviation Dr, DFW Airport, TX 75261'),
        ('Los Angeles Coastal Depot', 'LAX-03', 'Long Beach', 'CA', '1100 Ocean Blvd, Long Beach, CA 90802'),
        ('Atlanta Southeast Facility', 'ATL-04', 'Atlanta', 'GA', '3400 Southside Blvd, Atlanta, GA 30354'),
        ('New Jersey Tri-State Hub', 'NJ-05', 'Newark', 'NJ', '150 Port St, Newark, NJ 07114'),
    ]
    branches = {}
    for name, code, city, state, addr in branch_specs:
        b, _ = Branch.objects.get_or_create(
            tenant=tenant,
            code=code,
            defaults={'name': name, 'city': city, 'state': state, 'address': addr, 'is_active': True}
        )
        branches[code] = b
    print(f"[+] Seeded {len(branches)} Operating Branches")

    # 4. Vehicle Categories
    category_specs = [
        ('Heavy Haul Tractor Sleeper', 'HEAVY_TRACTOR', 'Class 8 line-haul tractor with sleeper cab'),
        ('Multi-Temp Refrigerated Unit', 'REEFER_COLD', 'Pharma and perishable cold storage with dual evap'),
        ('High-Cube 53ft Dry Van', 'DRY_VAN_53', 'High volume dry freight container trailer'),
        ('Urban Electric Cargo Van', 'EV_VAN', 'Zero-emission last-mile distribution electric vehicle'),
        ('Luxury 45-Passenger Coach', 'COACH_BUS', 'Intercity executive tourist coach'),
    ]
    categories = {}
    for name, code, desc in category_specs:
        cat, _ = VehicleCategory.objects.get_or_create(
            tenant=tenant,
            code=code,
            defaults={'name': name, 'description': desc}
        )
        categories[code] = cat
    print(f"[+] Seeded {len(categories)} Vehicle Categories")

    # 5. Drivers
    driver_specs = [
        ('Carlos', 'Mendoza', '+1-312-555-0101', 'carlos.mendoza@apexlogistics.com', 'DL-MEND-01', DriverStatus.ON_TRIP, date(2028, 5, 20)),
        ('Darius', 'Jackson', '+1-214-555-0102', 'darius.jackson@apexlogistics.com', 'DL-JACK-02', DriverStatus.AVAILABLE, date(2027, 9, 15)),
        ('Samantha', 'Reed', '+1-562-555-0103', 'samantha.reed@apexlogistics.com', 'DL-REED-03', DriverStatus.AVAILABLE, date(2029, 2, 10)),
        ('Michael', 'Zhang', '+1-404-555-0104', 'michael.zhang@apexlogistics.com', 'DL-ZHANG-04', DriverStatus.ON_TRIP, date(2027, 11, 30)),
        ('Tyrone', 'Washington', '+1-973-555-0105', 'tyrone.wash@apexlogistics.com', 'DL-WASH-05', DriverStatus.RESTING, date(2028, 8, 25)),
        ('Elena', 'Rostova', '+1-312-555-0106', 'elena.rostova@apexlogistics.com', 'DL-ROST-06', DriverStatus.AVAILABLE, date(2029, 4, 18)),
        ('Liam', "O'Connor", '+1-773-555-0107', 'liam.oconnor@apexlogistics.com', 'DL-OCON-07', DriverStatus.AVAILABLE, date(2027, 6, 12)),
        ('Javier', 'Morales', '+1-201-555-0108', 'javier.morales@apexlogistics.com', 'DL-MORA-08', DriverStatus.AVAILABLE, date(2028, 10, 5)),
    ]
    drivers = {}
    for first, last, phone, email, lic_no, status, expiry in driver_specs:
        d, _ = Driver.objects.get_or_create(
            tenant=tenant,
            license_number=lic_no,
            defaults={
                'first_name': first,
                'last_name': last,
                'phone': phone,
                'email': email,
                'license_expiry': expiry,
                'status': status,
            }
        )
        drivers[lic_no] = d

        # Seed Driver Document
        DriverDocument.objects.get_or_create(
            tenant=tenant,
            driver=d,
            document_type='COMMERCIAL_DRIVER_LICENSE',
            defaults={
                'document_number': lic_no,
                'issue_date': date(2023, 1, 15),
                'expiry_date': expiry,
                'is_verified': True,
            }
        )
    print(f"[+] Seeded {len(drivers)} Drivers with Compliance Licenses")

    # 6. Vehicles
    vehicle_specs = [
        {
            'reg': 'IL-9428-TX',
            'make': 'Volvo',
            'model': 'FH16 750 Reefer',
            'year': 2024,
            'vin': 'YV2RT40A5MA109823',
            'category': categories['REEFER_COLD'],
            'branch': branches['CHI-01'],
            'driver': drivers['DL-MEND-01'],
            'vertical': VehicleVertical.COLD_CHAIN,
            'type': VehicleType.REEFER_COLD,
            'status': VehicleStatus.ON_TRIP,
            'availability': VehicleAvailability.ASSIGNED,
            'ownership': VehicleOwnership.OWNED,
            'odometer': Decimal('84320.50'),
            'capacity': Decimal('24000.00'),
            'fuel_type': 'DIESEL',
            'fuel_pct': Decimal('78.00'),
            'oil_pct': Decimal('92.00'),
            'adblue_pct': Decimal('85.00'),
            'sensor': {
                'currentTempC': -19.4,
                'targetTempC': -20.0,
                'humidityPercent': 62,
                'status': 'normal'
            }
        },
        {
            'reg': 'IL-6102-FR',
            'make': 'Freightliner',
            'model': 'Cascadia 126 Sleeper',
            'year': 2023,
            'vin': '1FUJBBCK4NL892019',
            'category': categories['HEAVY_TRACTOR'],
            'branch': branches['DFW-02'],
            'driver': drivers['DL-JACK-02'],
            'vertical': VehicleVertical.FREIGHT_LOGISTICS,
            'type': VehicleType.HEAVY_TRUCK,
            'status': VehicleStatus.AVAILABLE,
            'availability': VehicleAvailability.AVAILABLE,
            'ownership': VehicleOwnership.OWNED,
            'odometer': Decimal('134200.00'),
            'capacity': Decimal('30000.00'),
            'fuel_type': 'DIESEL',
            'fuel_pct': Decimal('94.00'),
            'oil_pct': Decimal('88.00'),
            'adblue_pct': Decimal('90.00'),
            'sensor': {}
        },
        {
            'reg': 'CA-8831-EV',
            'make': 'Ford',
            'model': 'E-Transit 350 High Roof',
            'year': 2024,
            'vin': '1FTBW1Y88NKA12940',
            'category': categories['EV_VAN'],
            'branch': branches['LAX-03'],
            'driver': drivers['DL-REED-03'],
            'vertical': VehicleVertical.LAST_MILE,
            'type': VehicleType.MINI_TRUCK,
            'status': VehicleStatus.AVAILABLE,
            'availability': VehicleAvailability.AVAILABLE,
            'ownership': VehicleOwnership.LEASED,
            'odometer': Decimal('18450.00'),
            'capacity': Decimal('1750.00'),
            'fuel_type': 'ELECTRIC',
            'fuel_pct': Decimal('82.00'),
            'oil_pct': Decimal('100.00'),
            'adblue_pct': None,
            'sensor': {}
        },
        {
            'reg': 'TX-3319-CT',
            'make': 'Kenworth',
            'model': 'T680 Next Gen',
            'year': 2023,
            'vin': '1XKWDB9X8PR774910',
            'category': categories['DRY_VAN_53'],
            'branch': branches['DFW-02'],
            'driver': drivers['DL-ZHANG-04'],
            'vertical': VehicleVertical.B2B_CONTRACT,
            'type': VehicleType.CONTAINER,
            'status': VehicleStatus.ON_TRIP,
            'availability': VehicleAvailability.ASSIGNED,
            'ownership': VehicleOwnership.OWNED,
            'odometer': Decimal('92400.00'),
            'capacity': Decimal('28000.00'),
            'fuel_type': 'DIESEL',
            'fuel_pct': Decimal('65.00'),
            'oil_pct': Decimal('75.00'),
            'adblue_pct': Decimal('70.00'),
            'sensor': {}
        },
        {
            'reg': 'GA-5501-FL',
            'make': 'Peterbilt',
            'model': '579 UltraLoft',
            'year': 2022,
            'vin': '1XP5DB9X5ND902144',
            'category': categories['HEAVY_TRACTOR'],
            'branch': branches['ATL-04'],
            'driver': drivers['DL-WASH-05'],
            'vertical': VehicleVertical.HEAVY_MACHINERY,
            'type': VehicleType.FLATBED,
            'status': VehicleStatus.AVAILABLE,
            'availability': VehicleAvailability.AVAILABLE,
            'ownership': VehicleOwnership.ATTACHED,
            'odometer': Decimal('210500.00'),
            'capacity': Decimal('32000.00'),
            'fuel_type': 'DIESEL',
            'fuel_pct': Decimal('89.00'),
            'oil_pct': Decimal('60.00'),
            'adblue_pct': Decimal('80.00'),
            'sensor': {}
        },
        {
            'reg': 'NJ-2049-CR',
            'make': 'Mercedes-Benz',
            'model': 'Sprinter 3500 XD',
            'year': 2024,
            'vin': 'W1W4EBHY5NT091823',
            'category': categories['EV_VAN'],
            'branch': branches['NJ-05'],
            'driver': drivers['DL-MORA-08'],
            'vertical': VehicleVertical.COURIER_EXPRESS,
            'type': VehicleType.MINI_TRUCK,
            'status': VehicleStatus.AVAILABLE,
            'availability': VehicleAvailability.AVAILABLE,
            'ownership': VehicleOwnership.OWNED,
            'odometer': Decimal('34200.00'),
            'capacity': Decimal('2500.00'),
            'fuel_type': 'DIESEL',
            'fuel_pct': Decimal('74.00'),
            'oil_pct': Decimal('85.00'),
            'adblue_pct': Decimal('92.00'),
            'sensor': {}
        },
        {
            'reg': 'IL-7712-BS',
            'make': 'Prevost',
            'model': 'H3-45 Executive Coach',
            'year': 2023,
            'vin': '2PCG33499M1092841',
            'category': categories['COACH_BUS'],
            'branch': branches['CHI-01'],
            'driver': drivers['DL-OCON-07'],
            'vertical': VehicleVertical.CORPORATE_SHUTTLE,
            'type': VehicleType.BUS,
            'status': VehicleStatus.AVAILABLE,
            'availability': VehicleAvailability.AVAILABLE,
            'ownership': VehicleOwnership.LEASED,
            'odometer': Decimal('62800.00'),
            'capacity': Decimal('6000.00'),
            'fuel_type': 'DIESEL',
            'fuel_pct': Decimal('91.00'),
            'oil_pct': Decimal('90.00'),
            'adblue_pct': Decimal('95.00'),
            'sensor': {}
        },
        {
            'reg': 'CA-9941-RF',
            'make': 'Scania',
            'model': 'R500 Highline Reefer',
            'year': 2024,
            'vin': 'YS2R4X20002938174',
            'category': categories['REEFER_COLD'],
            'branch': branches['LAX-03'],
            'driver': drivers['DL-ROST-06'],
            'vertical': VehicleVertical.COLD_CHAIN,
            'type': VehicleType.REEFER_COLD,
            'status': VehicleStatus.AVAILABLE,
            'availability': VehicleAvailability.AVAILABLE,
            'ownership': VehicleOwnership.OWNED,
            'odometer': Decimal('41200.00'),
            'capacity': Decimal('22500.00'),
            'fuel_type': 'DIESEL',
            'fuel_pct': Decimal('98.00'),
            'oil_pct': Decimal('94.00'),
            'adblue_pct': Decimal('90.00'),
            'sensor': {
                'currentTempC': 3.8,
                'targetTempC': 4.0,
                'humidityPercent': 85,
                'status': 'normal'
            }
        },
    ]

    vehicles = {}
    for spec in vehicle_specs:
        v, _ = Vehicle.objects.get_or_create(
            tenant=tenant,
            registration_number=spec['reg'],
            defaults={
                'make': spec['make'],
                'model': spec['model'],
                'year': spec['year'],
                'vin': spec['vin'],
                'category': spec['category'],
                'branch': spec['branch'],
                'assigned_driver': spec['driver'],
                'vertical': spec['vertical'],
                'type': spec['type'],
                'status': spec['status'],
                'availability': spec['availability'],
                'ownership': spec['ownership'],
                'odometer_km': spec['odometer'],
                'capacity_kg': spec['capacity'],
                'fuel_type': spec['fuel_type'],
                'fuel_level_percent': spec['fuel_pct'],
                'engine_oil_life_percent': spec['oil_pct'],
                'ad_blue_level_percent': spec['adblue_pct'],
                'temperature_sensor': spec['sensor'],
            }
        )
        vehicles[spec['reg']] = v

        # Vehicle Documents
        VehicleDocument.objects.get_or_create(
            tenant=tenant,
            vehicle=v,
            document_type=DocumentType.INSURANCE,
            defaults={
                'document_number': f"POL-ALLIANZ-{spec['reg'].replace('-', '')}",
                'issue_date': date(2025, 10, 1),
                'expiry_date': date(2026, 10, 1),
                'status': DocumentStatus.VALID,
                'file_path': f"s3://omnicore-vault/{tenant.tenant_id}/docs/insurance_{spec['reg']}.pdf",
            }
        )
        VehicleDocument.objects.get_or_create(
            tenant=tenant,
            vehicle=v,
            document_type=DocumentType.REGISTRATION,
            defaults={
                'document_number': f"REG-{spec['reg']}",
                'issue_date': date(2024, 1, 1),
                'expiry_date': date(2027, 1, 1),
                'status': DocumentStatus.VALID,
                'file_path': f"s3://omnicore-vault/{tenant.tenant_id}/docs/rc_{spec['reg']}.pdf",
            }
        )

        # Vehicle Assignment record
        VehicleAssignment.objects.get_or_create(
            tenant=tenant,
            vehicle=v,
            driver=spec['driver'],
            defaults={
                'assigned_from': timezone.now() - timedelta(days=60),
                'is_active': True,
                'notes': f"Permanent assignment for {spec['vertical']} operations",
            }
        )
    print(f"[+] Seeded {len(vehicles)} Vehicles with Live Telemetry, Documents & Driver Assignments")

    # 7. Customers
    customer_specs = [
        ('Pfizer Global Biologics', 'Dr. Aris Thorne', 'supplychain@pfizer.com', '+1-212-555-0210', '100 Route 206, Peapack, NJ 07977', 'EIN-13-5315170', CustomerType.CORPORATE, Decimal('500000.00')),
        ('Amazon Logistics Middle Mile', 'Danielle Vance', 'middlemile-ops@amazon.com', '+1-206-555-0320', '410 Terry Ave N, Seattle, WA 98109', 'EIN-91-1646860', CustomerType.CORPORATE, Decimal('1000000.00')),
        ('Walmart Regional Distribution', 'Craig Miller', 'freightops@walmart.com', '+1-479-555-0430', '702 SW 8th St, Bentonville, AR 72716', 'EIN-71-0415188', CustomerType.CORPORATE, Decimal('750000.00')),
        ('Sysco Perishable Foods Corp', 'Robert Chen', 'logistics@sysco.com', '+1-281-555-0540', '1390 Enclave Pkwy, Houston, TX 77077', 'EIN-74-1627678', CustomerType.CORPORATE, Decimal('350000.00')),
        ('Target Regional Supply Chain', 'Laura Becker', 'inbound@target.com', '+1-612-555-0650', '1000 Nicollet Mall, Minneapolis, MN 55403', 'EIN-41-0215170', CustomerType.CORPORATE, Decimal('400000.00')),
    ]
    customers = {}
    for c_name, contact, email, phone, addr, tax_id, c_type, credit in customer_specs:
        c, _ = Customer.objects.get_or_create(
            tenant=tenant,
            company_name=c_name,
            defaults={
                'contact_person': contact,
                'email': email,
                'phone': phone,
                'address': addr,
                'tax_id': tax_id,
                'customer_type': c_type,
                'credit_limit': credit,
                'payment_terms_days': 30,
                'is_active': True,
            }
        )
        customers[c_name] = c
    print(f"[+] Seeded {len(customers)} Enterprise Customers")

    # 8. Routes
    route_specs = [
        ('Chicago to Dallas Express Corridor', 'Chicago Central Depot, IL', 'Dallas-Fort Worth Linehaul Hub, TX', Decimal('1495.00'), Decimal('17.50'), 4),
        ('Los Angeles to Phoenix Fastlane', 'Los Angeles Port, Long Beach, CA', 'Phoenix Logistics Center, AZ', Decimal('610.00'), Decimal('6.50'), 1),
        ('Atlanta to Charlotte Southeast Sprint', 'Atlanta Southeast Facility, GA', 'Charlotte Distribution Yard, NC', Decimal('395.00'), Decimal('4.25'), 2),
        ('Chicago to Des Moines Freight Route', 'Chicago Central Depot, IL', 'Des Moines Regional Hub, IA', Decimal('535.00'), Decimal('5.50'), 1),
    ]
    routes = {}
    for r_name, orig, dest, dist, hours, tolls in route_specs:
        r, _ = Route.objects.get_or_create(
            tenant=tenant,
            name=r_name,
            defaults={
                'origin': orig,
                'destination': dest,
                'standard_distance_km': dist,
                'estimated_hours': hours,
                'toll_points_count': tolls,
            }
        )
        routes[r_name] = r
    print(f"[+] Seeded {len(routes)} Transport Corridors / Routes")

    # 9. Bookings & Trips
    # Active Trip 1: IL-9428-TX with Carlos Mendoza (Pharma Cold Chain)
    booking1, _ = Booking.objects.get_or_create(
        tenant=tenant,
        booking_number='BKG-2026-0901',
        defaults={
            'customer': customers['Pfizer Global Biologics'],
            'pickup_location': 'Pfizer Peapack R&D Center, NJ',
            'dropoff_location': 'Northwestern Memorial Hospital, Chicago, IL',
            'cargo_type': 'mRNA Vaccines & Biologics (-20°C Reefer)',
            'cargo_weight_kg': Decimal('8500.00'),
            'scheduled_date': date.today(),
            'commercial_rate': Decimal('9850.00'),
            'status': BookingStatus.ALLOCATED,
        }
    )

    trip1, _ = Trip.objects.get_or_create(
        tenant=tenant,
        trip_number='TRIP-2026-9001',
        defaults={
            'customer': customers['Pfizer Global Biologics'],
            'booking': booking1,
            'vehicle': vehicles['IL-9428-TX'],
            'driver': drivers['DL-MEND-01'],
            'route': routes['Chicago to Dallas Express Corridor'],
            'origin': 'Peapack, NJ',
            'destination': 'Chicago, IL',
            'scheduled_start': timezone.now() - timedelta(hours=8),
            'actual_start': timezone.now() - timedelta(hours=7, minutes=30),
            'start_odometer': Decimal('83720.00'),
            'distance_km': Decimal('600.00'),
            'freight_charge': Decimal('9850.00'),
            'advance_paid': Decimal('2000.00'),
            'status': TripStatus.IN_PROGRESS,
            'notes': 'High priority temperature-monitored pharmaceutical consignment',
        }
    )
    TripExpense.objects.get_or_create(
        tenant=tenant,
        trip=trip1,
        receipt_number='EXP-FUEL-9001',
        defaults={
            'expense_type': TripExpenseType.FUEL,
            'amount': Decimal('420.50'),
            'notes': 'Ulta-low sulfur diesel fill up at TravelCenters of America, Mile 142',
            'is_approved': True,
        }
    )

    # Active Trip 2: TX-3319-CT with Michael Zhang (B2B Container)
    booking2, _ = Booking.objects.get_or_create(
        tenant=tenant,
        booking_number='BKG-2026-0902',
        defaults={
            'customer': customers['Amazon Logistics Middle Mile'],
            'pickup_location': 'DFW Fulfillment Yard 4, TX',
            'dropoff_location': 'Amazon MDW2 Hub, Joliet, IL',
            'cargo_type': 'High-Density Sortation Pallets',
            'cargo_weight_kg': Decimal('21000.00'),
            'scheduled_date': date.today(),
            'commercial_rate': Decimal('6450.00'),
            'status': BookingStatus.ALLOCATED,
        }
    )

    trip2, _ = Trip.objects.get_or_create(
        tenant=tenant,
        trip_number='TRIP-2026-9002',
        defaults={
            'customer': customers['Amazon Logistics Middle Mile'],
            'booking': booking2,
            'vehicle': vehicles['TX-3319-CT'],
            'driver': drivers['DL-ZHANG-04'],
            'route': routes['Chicago to Dallas Express Corridor'],
            'origin': 'DFW Airport, TX',
            'destination': 'Joliet, IL',
            'scheduled_start': timezone.now() - timedelta(hours=14),
            'actual_start': timezone.now() - timedelta(hours=13),
            'start_odometer': Decimal('91500.00'),
            'distance_km': Decimal('900.00'),
            'freight_charge': Decimal('6450.00'),
            'advance_paid': Decimal('1500.00'),
            'status': TripStatus.IN_PROGRESS,
            'notes': 'Amazon Prime line-haul scheduled run',
        }
    )

    # Completed Trip: IL-6102-FR with Darius Jackson
    trip3, _ = Trip.objects.get_or_create(
        tenant=tenant,
        trip_number='TRIP-2026-8995',
        defaults={
            'customer': customers['Walmart Regional Distribution'],
            'vehicle': vehicles['IL-6102-FR'],
            'driver': drivers['DL-JACK-02'],
            'route': routes['Chicago to Des Moines Freight Route'],
            'origin': 'Chicago Central Depot, IL',
            'destination': 'Des Moines, IA',
            'scheduled_start': timezone.now() - timedelta(days=2, hours=10),
            'actual_start': timezone.now() - timedelta(days=2, hours=9),
            'actual_end': timezone.now() - timedelta(days=1, hours=18),
            'start_odometer': Decimal('133665.00'),
            'end_odometer': Decimal('134200.00'),
            'distance_km': Decimal('535.00'),
            'freight_charge': Decimal('3200.00'),
            'advance_paid': Decimal('800.00'),
            'status': TripStatus.COMPLETED,
            'notes': 'Completed on time, POD verified',
        }
    )
    print(f"[+] Seeded Bookings, Active In-Progress Trips, and Completed Trip History")

    # 10. Warehouses & Supply Chain
    wh1, _ = Warehouse.objects.get_or_create(
        tenant=tenant,
        code='WH-CHI-MAIN',
        defaults={
            'name': 'Apex Central Transshipment Crossdock',
            'address': '4200 W 47th St, Bay 1-20, Chicago, IL 60632',
            'is_active': True,
        }
    )
    wh2, _ = Warehouse.objects.get_or_create(
        tenant=tenant,
        code='WH-DFW-COLD',
        defaults={
            'name': 'DFW Sub-Zero Cold Chain Distribution Facility',
            'address': '2400 Aviation Dr, Building B, DFW Airport, TX 75261',
            'is_active': True,
        }
    )

    sup1, _ = Supplier.objects.get_or_create(
        tenant=tenant,
        code='SUP-MICHELIN',
        defaults={
            'name': 'Michelin Commercial Fleet Solutions',
            'contact_person': 'Greg Sanderson',
            'email': 'fleet.orders@michelin.com',
            'phone': '+1-800-555-0190',
            'address': '1000 Michelin Rd, Greenville, SC 29605',
        }
    )
    sup2, _ = Supplier.objects.get_or_create(
        tenant=tenant,
        code='SUP-MOBIL',
        defaults={
            'name': 'ExxonMobil Lubricants Industrial',
            'contact_person': 'Sarah Jenkins',
            'email': 'delvac.orders@exxonmobil.com',
            'phone': '+1-800-555-0180',
            'address': '22777 Springwoods Village Pkwy, Spring, TX 77389',
        }
    )

    SparePart.objects.get_or_create(
        tenant=tenant,
        part_number='TYR-MICH-X-LINE',
        defaults={
            'name': 'Michelin X Line Energy D 275/80R22.5 Tire',
            'category': 'TIRES',
            'unit': 'PCS',
            'unit_cost': Decimal('620.00'),
            'current_stock': Decimal('48.00'),
            'minimum_stock': Decimal('10.00'),
            'reorder_level': Decimal('16.00'),
        }
    )
    SparePart.objects.get_or_create(
        tenant=tenant,
        part_number='OIL-MOBIL-DELVAC-1',
        defaults={
            'name': 'Mobil Delvac 1 ESP 5W-40 Synthetic Oil (55 Gal Drum)',
            'category': 'LUBRICANTS',
            'unit': 'DRUM',
            'unit_cost': Decimal('1250.00'),
            'current_stock': Decimal('12.00'),
            'minimum_stock': Decimal('2.00'),
            'reorder_level': Decimal('4.00'),
        }
    )
    print(f"[+] Seeded Warehouses, Suppliers & Spare Parts Inventory")

    # 11. Maintenance Schedules & Records
    MaintenanceSchedule.objects.get_or_create(
        tenant=tenant,
        vehicle=vehicles['IL-6102-FR'],
        defaults={
            'interval_km': 40000,
            'interval_days': 120,
            'last_service_date': date.today() - timedelta(days=35),
            'last_service_odometer': Decimal('125000.00'),
            'next_due_date': date.today() + timedelta(days=85),
            'next_due_odometer': Decimal('165000.00'),
            'is_active': True,
        }
    )
    MaintenanceRecord.objects.get_or_create(
        tenant=tenant,
        vehicle=vehicles['IL-6102-FR'],
        performed_date=date.today() - timedelta(days=35),
        defaults={
            'service_type': ServiceType.OIL_CHANGE,
            'odometer_reading': Decimal('125000.00'),
            'service_center': 'Freightliner Trucks Chicago West Service Center',
            'cost': Decimal('780.00'),
            'notes': 'Replaced engine oil with Mobil Delvac synthetic and OEM Fleetguard filters',
        }
    )
    print(f"[+] Seeded Maintenance Schedules & Service Records")

    # 12. Insurance Policies
    InsurancePolicy.objects.get_or_create(
        tenant=tenant,
        policy_number='POL-COMM-ALLIANZ-88219',
        defaults={
            'provider_name': 'Allianz Global Corporate & Specialty',
            'policy_type': PolicyType.COMPREHENSIVE,
            'vehicle': vehicles['IL-9428-TX'],
            'start_date': date(2025, 10, 1),
            'end_date': date(2026, 10, 1),
            'premium_amount': Decimal('4800.00'),
            'coverage_amount': Decimal('1500000.00'),
            'status': 'ACTIVE',
        }
    )
    InsurancePolicy.objects.get_or_create(
        tenant=tenant,
        policy_number='POL-CARGO-TRAVELERS-99301',
        defaults={
            'provider_name': 'Travelers Marine & Cold Spoilage Underwriters',
            'policy_type': PolicyType.CARGO,
            'vehicle': vehicles['IL-9428-TX'],
            'start_date': date(2025, 5, 15),
            'end_date': date(2026, 11, 15),
            'premium_amount': Decimal('6200.00'),
            'coverage_amount': Decimal('2500000.00'),
            'status': 'ACTIVE',
        }
    )
    print(f"[+] Seeded Commercial Fleet & Cold Spoilage Cargo Insurance Policies")

    # 13. Contracts
    Contract.objects.get_or_create(
        tenant=tenant,
        contract_number='CTR-2026-PFZ-01',
        defaults={
            'title': 'Master Pharmaceutical Cold-Chain Dedicated Transport Agreement',
            'customer': customers['Pfizer Global Biologics'],
            'start_date': date(2026, 1, 1),
            'end_date': date(2027, 12, 31),
            'total_contract_value': Decimal('1850000.00'),
            'minimum_monthly_commitment': Decimal('65000.00'),
            'payment_terms_days': 30,
            'status': ContractStatus.ACTIVE,
            'terms_and_conditions': 'Pharma-grade GDP certified cold chain line-haul transport with dual-satellite live logging',
        }
    )
    Contract.objects.get_or_create(
        tenant=tenant,
        contract_number='CTR-2026-AMZ-02',
        defaults={
            'title': 'Amazon Middle-Mile Corridor Transportation Contract',
            'customer': customers['Amazon Logistics Middle Mile'],
            'start_date': date(2026, 3, 1),
            'end_date': date(2027, 2, 28),
            'total_contract_value': Decimal('3200000.00'),
            'minimum_monthly_commitment': Decimal('120000.00'),
            'payment_terms_days': 15,
            'status': ContractStatus.ACTIVE,
            'terms_and_conditions': 'Guaranteed line-haul trailer relays connecting Chicago, DFW and Atlanta sortation centers',
        }
    )
    print(f"[+] Seeded Long-Term Enterprise Dedicated Contracts")

    print("\n=======================================================")
    print("      SAMPLE DATA SEEDING COMPLETE FOR ALL MODELS!     ")
    print("=======================================================\n")


if __name__ == '__main__':
    seed_data()
