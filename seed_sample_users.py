import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.accounts.models import User, PlatformRole
from apps.tenants.models import Tenant, Role, TenantUser, Permission

DEFAULT_PASSWORD = 'admin'

# 1. Ensure primary tenant exists
tenant = Tenant.objects.first()
if not tenant:
    tenant = Tenant.objects.create(
        tenant_id='OCT-100001',
        company_name='Apex Global Logistics & Cold Chain',
        slug='apex-global',
        status='active',
        primary_contact_name='Marcus Sterling',
        primary_contact_email='sarang@apexlogistics.com',
    )
print(f"Using Tenant: {tenant.company_name} (ID: {tenant.tenant_id}, UUID: {tenant.id})")

# 2. Platform-Level Users to create
platform_users = [
    {
        'email': 'superadmin@omnicore.io',
        'first_name': 'Alexander',
        'last_name': 'Vance',
        'is_superuser': True,
        'is_staff': True,
        'is_platform_admin': True,
        'platform_role': PlatformRole.SUPER_ADMIN,
        'title': 'Platform Super Admin',
    },
    {
        'email': 'admin@gmail.com',  # Existing admin alias
        'first_name': 'Admin',
        'last_name': 'Platform',
        'is_superuser': True,
        'is_staff': True,
        'is_platform_admin': True,
        'platform_role': PlatformRole.SUPER_ADMIN,
        'title': 'Platform Super Admin (Alias)',
    },
    {
        'email': 'salesadmin@omnicore.io',
        'first_name': 'Victoria',
        'last_name': 'Sterling',
        'is_superuser': False,
        'is_staff': True,
        'is_platform_admin': True,
        'platform_role': PlatformRole.SALES_ADMIN,
        'title': 'Platform Sales Administrator',
    },
    {
        'email': 'financeadmin@omnicore.io',
        'first_name': 'Jonathan',
        'last_name': 'Hayes',
        'is_superuser': False,
        'is_staff': True,
        'is_platform_admin': True,
        'platform_role': PlatformRole.FINANCE_ADMIN,
        'title': 'Platform Finance Administrator',
    },
    {
        'email': 'supportadmin@omnicore.io',
        'first_name': 'Clara',
        'last_name': 'Oswald',
        'is_superuser': False,
        'is_staff': True,
        'is_platform_admin': True,
        'platform_role': PlatformRole.SUPPORT_ADMIN,
        'title': 'Platform Support Administrator',
    },
    {
        'email': 'auditor@omnicore.io',
        'first_name': 'Robert',
        'last_name': 'Langdon',
        'is_superuser': False,
        'is_staff': True,
        'is_platform_admin': True,
        'platform_role': PlatformRole.PLATFORM_AUDITOR,
        'title': 'Platform Auditor (Read-Only)',
    },
]

print("\n--- Seeding Platform Users ---")
for pu in platform_users:
    user, created = User.objects.get_or_create(
        email=pu['email'].lower(),
        defaults={
            'first_name': pu['first_name'],
            'last_name': pu['last_name'],
            'is_superuser': pu['is_superuser'],
            'is_staff': pu['is_staff'],
            'is_platform_admin': pu['is_platform_admin'],
            'platform_role': pu['platform_role'],
            'is_mfa_enabled': False,
        }
    )
    user.set_password(DEFAULT_PASSWORD)
    user.first_name = pu['first_name']
    user.last_name = pu['last_name']
    user.is_superuser = pu['is_superuser']
    user.is_staff = pu['is_staff']
    user.is_platform_admin = pu['is_platform_admin']
    user.platform_role = pu['platform_role']
    user.is_mfa_enabled = False
    user.save()
    status_str = "Created" if created else "Updated"
    print(f"[{status_str}] {pu['title']}: {user.email} (Password: {DEFAULT_PASSWORD})")


# 3. Tenant-Level Users to create
tenant_users_specs = [
    {
        'email': 'sarang@apexlogistics.com',
        'first_name': 'Marcus',
        'last_name': 'Sterling',
        'role_code': 'TENANT_ADMIN',
        'title': 'Tenant Administrator (Default)',
    },
    {
        'email': 'tenantadmin@apexlogistics.com',
        'first_name': 'Marcus',
        'last_name': 'Sterling',
        'role_code': 'TENANT_ADMIN',
        'title': 'Tenant Administrator',
    },
    {
        'email': 'operations@apexcargo.com',
        'first_name': 'Elena',
        'last_name': 'Rostova',
        'role_code': 'OPERATIONS_MANAGER',
        'title': 'Operations Manager (Default)',
    },
    {
        'email': 'opsmanager@apexlogistics.com',
        'first_name': 'Elena',
        'last_name': 'Rostova',
        'role_code': 'OPERATIONS_MANAGER',
        'title': 'Operations Manager',
    },
    {
        'email': 'fleetmanager@apexlogistics.com',
        'first_name': 'Carlos',
        'last_name': 'Mendez',
        'role_code': 'FLEET_MANAGER',
        'title': 'Fleet Manager',
    },
    {
        'email': 'finance@apexlogistics.com',
        'first_name': 'Julian',
        'last_name': 'Vance',
        'role_code': 'FINANCE_USER',
        'title': 'Finance & Billing User (Default)',
    },
    {
        'email': 'financeuser@apexlogistics.com',
        'first_name': 'Julian',
        'last_name': 'Vance',
        'role_code': 'FINANCE_USER',
        'title': 'Finance & Billing User',
    },
    {
        'email': 'hruser@apexlogistics.com',
        'first_name': 'Sophia',
        'last_name': 'Turner',
        'role_code': 'HR_USER',
        'title': 'HR & Payroll User',
    },
    {
        'email': 'warehouseuser@apexlogistics.com',
        'first_name': 'David',
        'last_name': 'Kowalski',
        'role_code': 'WAREHOUSE_USER',
        'title': 'Warehouse & Inventory User',
    },
    {
        'email': 'salesuser@apexlogistics.com',
        'first_name': 'Natasha',
        'last_name': 'Romanoff',
        'role_code': 'SALES_CRM_USER',
        'title': 'Sales & CRM User',
    },
    {
        'email': 'driveruser@apexlogistics.com',
        'first_name': 'James',
        'last_name': 'Wilson',
        'role_code': 'DRIVER_FIELD_USER',
        'title': 'Driver & Field User',
    },
    {
        'email': 'driver@apexlogistics.com',
        'first_name': 'James',
        'last_name': 'Wilson',
        'role_code': 'DRIVER_FIELD_USER',
        'title': 'Driver & Field User (Alias)',
    },
]

print("\n--- Seeding Tenant Users ---")
for tu in tenant_users_specs:
    user, created = User.objects.get_or_create(
        email=tu['email'].lower(),
        defaults={
            'first_name': tu['first_name'],
            'last_name': tu['last_name'],
            'is_platform_admin': False,
            'platform_role': PlatformRole.NONE,
            'is_mfa_enabled': False,
        }
    )
    user.set_password(DEFAULT_PASSWORD)
    user.first_name = tu['first_name']
    user.last_name = tu['last_name']
    user.is_platform_admin = False
    user.platform_role = PlatformRole.NONE
    user.is_mfa_enabled = False
    user.save()

    # Link to Role & Tenant
    role = Role.objects.filter(code=tu['role_code']).first()
    if not role:
        role = Role.objects.create(
            code=tu['role_code'],
            name=tu['title'],
            is_system_role=True
        )

    membership, m_created = TenantUser.objects.get_or_create(
        tenant=tenant,
        user=user,
        defaults={
            'role': role,
            'is_primary': True,
            'is_active': True,
        }
    )
    membership.role = role
    membership.is_primary = True
    membership.is_active = True
    membership.save()

    perms_count = membership.get_all_permissions()
    print(f"[{'Created' if created else 'Updated'}] {tu['title']} ({tu['role_code']}): {user.email} -> {len(perms_count)} permissions")

print("\n=== All sample users successfully seeded into SQLite! ===")
