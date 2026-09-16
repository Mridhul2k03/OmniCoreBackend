import random
import string
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify
from django.contrib.auth import get_user_model
from apps.tenants.models import (
    Tenant,
    TenantStatus,
    TenantUser,
    Role,
    Permission,
    RolePermission,
    Vertical,
    TenantRoleCode
)
from apps.subscriptions.models import (
    Package,
    Addon,
    Subscription,
    SubscriptionStatus,
    BillingCycle
)
from apps.subscriptions.services import sync_tenant_features
from apps.audit.services import AuditService
from apps.core.exceptions import BusinessValidationError

User = get_user_model()


STANDARD_PERMISSIONS = [
    # Fleet
    ('vehicle.view', 'View Vehicles', 'fleet'),
    ('vehicle.create', 'Create Vehicles', 'fleet'),
    ('vehicle.update', 'Update Vehicles', 'fleet'),
    ('vehicle.delete', 'Delete Vehicles', 'fleet'),
    # Drivers
    ('driver.view', 'View Drivers', 'drivers'),
    ('driver.create', 'Create Drivers', 'drivers'),
    ('driver.update', 'Update Drivers', 'drivers'),
    ('driver.assign', 'Assign Drivers', 'drivers'),
    # Trips & Bookings
    ('trip.view', 'View Trips & Bookings', 'trips'),
    ('trip.create', 'Create Trips & Bookings', 'trips'),
    ('trip.dispatch', 'Dispatch Trips', 'trips'),
    ('trip.complete', 'Complete Trips', 'trips'),
    ('trip.cancel', 'Cancel Trips', 'trips'),
    # Contracts
    ('contract.view', 'View Contracts & Tenders', 'contracts'),
    ('contract.create', 'Create Contracts & Tenders', 'contracts'),
    ('contract.approve', 'Approve Contracts & Tenders', 'contracts'),
    # Maintenance
    ('maintenance.view', 'View Maintenance', 'maintenance'),
    ('maintenance.create', 'Create Maintenance Orders', 'maintenance'),
    # Warehouse
    ('warehouse.view', 'View Warehouse & Inventory', 'warehouse'),
    ('inventory.adjust', 'Adjust Inventory Stock', 'warehouse'),
    ('po.create', 'Create Purchase Orders', 'warehouse'),
    # Finance
    ('finance.view', 'View Invoices & Financials', 'finance'),
    ('invoice.create', 'Create Invoices', 'finance'),
    ('payment.record', 'Record Payments', 'finance'),
    ('pnl.view', 'View P&L Reports', 'finance'),
    # HR & Payroll
    ('hr.view', 'View Employees', 'hr'),
    ('payroll.view', 'View Payroll & Salaries', 'hr'),
    ('payroll.manage', 'Manage Payroll & Salaries', 'hr'),
    # CRM
    ('crm.view', 'View Customers & Leads', 'crm'),
    ('crm.manage', 'Manage CRM & Quotations', 'crm'),
    # Insurance
    ('insurance.view', 'View Insurance & Compliance', 'insurance'),
    ('insurance.manage', 'Manage Insurance & Claims', 'insurance'),
    # Audit & Settings
    ('audit.view', 'View Audit Logs', 'audit'),
    ('tenant.manage', 'Manage Tenant Settings', 'tenants'),
    # Courier & Express Delivery
    ('courier.view', 'View Courier Shipments & Hubs', 'courier'),
    ('courier.create', 'Create Courier Shipments & Pickups', 'courier'),
    ('courier.sort', 'Operate Hub Sorting', 'courier'),
    ('courier.dispatch', 'Dispatch Hub Shipments', 'courier'),
    ('courier.deliver', 'Execute Delivery & PoD', 'courier'),
    ('courier.payout', 'Manage Courier Payouts', 'courier'),
    # School & Corporate Shuttle
    ('shuttle.view', 'View Shuttle Operations', 'shuttle'),
    ('shuttle.manage', 'Manage Shuttle Routes & Schedules', 'shuttle'),
    ('shuttle.attendance', 'Record Shuttle Attendance', 'shuttle'),
    # Dynamic Website & Social
    ('website.manage', 'Manage Dynamic Mini-Website', 'website'),
    ('marketing.social', 'Manage Social Media Campaigns', 'marketing'),
    # Warehouse Cross-Dock & Consolidation
    ('warehouse.crossdock', 'Operate Warehouse Cross-Docking & Consolidation', 'warehouse'),
]


def seed_platform_roles_and_permissions():
    """
    Ensures all platform permissions and standard roles exist.
    """
    perm_objs = {}
    for code, name, module in STANDARD_PERMISSIONS:
        perm, _ = Permission.objects.get_or_create(
            code=code,
            defaults={'name': name, 'module': module}
        )
        perm_objs[code] = perm

    # Predefined System Roles (tenant=None)
    role_specs = {
        TenantRoleCode.TENANT_ADMIN: list(perm_objs.keys()),
        TenantRoleCode.OPERATIONS_MANAGER: [
            'vehicle.view', 'driver.view', 'driver.assign', 'trip.view',
            'trip.create', 'trip.dispatch', 'trip.complete', 'contract.view',
            'maintenance.view', 'warehouse.view', 'crm.view'
        ],
        TenantRoleCode.FLEET_MANAGER: [
            'vehicle.view', 'vehicle.create', 'vehicle.update', 'driver.view',
            'driver.assign', 'maintenance.view', 'maintenance.create', 'insurance.view'
        ],
        TenantRoleCode.FINANCE_USER: [
            'finance.view', 'invoice.create', 'payment.record', 'pnl.view',
            'trip.view', 'contract.view'
        ],
        TenantRoleCode.HR_USER: [
            'hr.view', 'payroll.view', 'payroll.manage', 'driver.view'
        ],
        TenantRoleCode.WAREHOUSE_USER: [
            'warehouse.view', 'inventory.adjust', 'po.create', 'maintenance.view'
        ],
        TenantRoleCode.SALES_CRM_USER: [
            'crm.view', 'crm.manage', 'contract.view', 'contract.create', 'trip.view'
        ],
        TenantRoleCode.DRIVER_FIELD_USER: [
            'trip.view', 'vehicle.view'
        ],
    }

    for role_code, perms in role_specs.items():
        role, _ = Role.objects.get_or_create(
            tenant=None,
            code=role_code,
            defaults={
                'name': role_code.label,
                'is_system_role': True,
                'description': f"Standard {role_code.label} role"
            }
        )
        for p_code in perms:
            if p_code in perm_objs:
                RolePermission.objects.get_or_create(role=role, permission=perm_objs[p_code])


class TenantProvisioningService:
    """
    Atomic and idempotent enterprise tenant provisioning service.
    """
    @staticmethod
    def generate_tenant_id() -> str:
        suffix = ''.join(random.choices(string.digits, k=6))
        return f"OCT-{suffix}"

    @classmethod
    def provision(
        cls,
        company_name: str,
        admin_email: str,
        admin_password: str,
        admin_first_name: str = 'Admin',
        admin_last_name: str = 'User',
        package_code: str = 'CORPORATE',
        addon_codes: list = None,
        vertical_codes: list = None,
        phone: str = '',
        address: str = '',
        billing_cycle: str = 'MONTHLY',
        actor=None
    ) -> dict:
        """
        Executes complete transactional provisioning workflow:
        1. Validate & create Tenant with unique ID & Slug
        2. Assign Verticals
        3. Assign Package & Addons
        4. Create Subscription
        5. Synchronize SaaS access & features
        6. Create or fetch Admin User
        7. Create TenantUser membership with TENANT_ADMIN role
        8. Activate Tenant
        9. Emit immutable Audit Log
        """
        addon_codes = addon_codes or []
        vertical_codes = vertical_codes or []

        with transaction.atomic():
            # Generate unique slug
            base_slug = slugify(company_name) or 'company'
            slug = base_slug
            counter = 1
            while Tenant.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1

            # Generate unique Tenant ID
            tenant_id = cls.generate_tenant_id()
            while Tenant.objects.filter(tenant_id=tenant_id).exists():
                tenant_id = cls.generate_tenant_id()

            # Resolve Package
            package = Package.objects.filter(code=package_code, is_active=True).first()
            if not package:
                # Seed packages if not yet present
                from apps.subscriptions.models import PackageTier
                package, _ = Package.objects.get_or_create(
                    code=package_code,
                    defaults={'name': f"OmniCore {package_code.capitalize()}", 'price_monthly': 299.00}
                )

            # 1. Create Tenant
            tenant = Tenant.objects.create(
                tenant_id=tenant_id,
                company_name=company_name,
                slug=slug,
                email=admin_email,
                phone=phone,
                address=address,
                status=TenantStatus.PROVISIONING,
                package=package
            )

            # 2. Assign Verticals
            for v_code in vertical_codes:
                vertical, _ = Vertical.objects.get_or_create(
                    code=v_code,
                    defaults={'name': v_code.replace('_', ' ').title()}
                )
                tenant.verticals.add(vertical)

            # 3. Create Subscription & Assign Addons
            now = timezone.now()
            period_end = now + timezone.timedelta(days=30 if billing_cycle == 'MONTHLY' else 365)
            subscription = Subscription.objects.create(
                tenant=tenant,
                package=package,
                billing_cycle=billing_cycle,
                status=SubscriptionStatus.ACTIVE,
                current_period_start=now,
                current_period_end=period_end,
                trial_end=now + timezone.timedelta(days=14)
            )

            for a_code in addon_codes:
                addon = Addon.objects.filter(code=a_code, is_active=True).first()
                if addon:
                    subscription.addons.add(addon)

            # 4. Synchronize SaaS access and feature entitlements
            sync_tenant_features(tenant)

            # 5. Ensure System Roles exist
            seed_platform_roles_and_permissions()
            admin_role = Role.objects.filter(code=TenantRoleCode.TENANT_ADMIN, tenant=None).first()

            # 6. Create initial Tenant Admin User
            admin_user, created = User.objects.get_or_create(
                email=admin_email.lower(),
                defaults={
                    'first_name': admin_first_name,
                    'last_name': admin_last_name,
                    'phone': phone,
                    'is_active': True,
                }
            )
            if created:
                admin_user.set_password(admin_password)
                admin_user.save()

            # 7. Create TenantUser membership
            TenantUser.objects.create(
                tenant=tenant,
                user=admin_user,
                role=admin_role,
                is_primary=True,
                is_active=True
            )

            # 8. Activate Tenant
            tenant.status = TenantStatus.ACTIVE
            tenant.activated_at = now
            tenant.save(update_fields=['status', 'activated_at'])

            # 9. Record Audit Log
            AuditService.record(
                actor=actor or admin_user,
                tenant=tenant,
                action='TENANT_PROVISIONED',
                target_type='Tenant',
                target_id=str(tenant.id),
                after_snapshot={
                    'tenant_id': tenant.tenant_id,
                    'company_name': tenant.company_name,
                    'slug': tenant.slug,
                    'package': package.code,
                    'status': tenant.status,
                    'admin_email': admin_email
                },
                metadata={'addons': addon_codes, 'verticals': vertical_codes}
            )

            return {
                'tenant': tenant,
                'admin_user': admin_user,
                'subscription': subscription,
                'tenant_id': tenant.tenant_id,
                'slug': tenant.slug,
            }
