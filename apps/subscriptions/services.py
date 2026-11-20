from decimal import Decimal
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from apps.subscriptions.models import (
    Feature,
    Package,
    Addon,
    TenantFeature,
    TenantFeatureOverride,
    Subscription,
    SubscriptionStatus,
)
from apps.audit.services import AuditService
from apps.core.exceptions import BusinessValidationError


PACKAGE_FEATURE_MINIMUM_TIER = {
    # Contracts are part of the Standard package and inherited by higher tiers.
    'contracts': {'STANDARD', 'CORPORATE', 'ENTERPRISE'},
    # Warehouse inventory is included from Corporate upward; Basic and Standard
    # tenants can enable it with the warehouse add-on.
    'warehouse': {'CORPORATE', 'ENTERPRISE'},
}


def tenant_has_feature(tenant, feature_code: str) -> bool:
    r"""
    Evaluates effective feature entitlement with override precedence:
    effective_features = (Package Features ∪ Active Add-ons) \ {Disabled Overrides} ∪ {Enabled Overrides}
    """
    if not tenant:
        return False

    now = timezone.now()

    # 1. Check custom feature overrides (highest precedence)
    override = TenantFeatureOverride.objects.filter(
        tenant=tenant,
        feature__code=feature_code
    ).first()

    if override:
        if override.expires_at and override.expires_at < now:
            # Expired override, fallback to standard package/addon
            pass
        else:
            return override.enabled

    # Explicit synchronized entitlement rows take precedence over package defaults.
    # This also preserves intentional per-tenant disabled states.
    entitlement = TenantFeature.objects.filter(
        tenant=tenant, feature__code=feature_code
    ).first()
    if entitlement:
        cache.set(f"tenant_feature_{tenant.id}_{feature_code}", entitlement.is_enabled, timeout=300)
        return entitlement.is_enabled

    package_code = ''
    subscription = Subscription.objects.filter(tenant=tenant).select_related('package').first()
    if subscription:
        package_code = subscription.package.code
    elif tenant.package_id:
        package_code = tenant.package.code

    if package_code in PACKAGE_FEATURE_MINIMUM_TIER.get(feature_code, set()):
        cache.set(f"tenant_feature_{tenant.id}_{feature_code}", True, timeout=300)
        return True

    if feature_code == 'contracts' and subscription and subscription.addons.filter(code='addon_contracts', is_active=True).exists():
        cache.set(f"tenant_feature_{tenant.id}_{feature_code}", True, timeout=300)
        return True

    # 3. Check cached standard entitlement
    cache_key = f"tenant_feature_{tenant.id}_{feature_code}"
    cached_result = cache.get(cache_key)
    if cached_result is not None:
        return cached_result

    # 4. Check legacy or explicitly assigned package/add-on features.
    has_entitlement = TenantFeature.objects.filter(
        tenant=tenant,
        feature__code=feature_code,
        is_enabled=True
    ).exists()

    cache.set(cache_key, has_entitlement, timeout=300)
    return has_entitlement


def get_tenant_effective_features(tenant) -> dict:
    """
    Returns full breakdown of tenant entitlements:
    - effective_features
    - package_features
    - addon_features
    - overrides
    """
    if not tenant:
        return {
            'effective_features': [],
            'package_features': [],
            'addon_features': [],
            'overrides': []
        }

    now = timezone.now()

    subscription = Subscription.objects.filter(tenant=tenant).select_related('package').first()
    package = subscription.package if subscription else tenant.package

    # Package features
    package_features = []
    if package:
        package_features = list(
            Feature.objects.filter(packages=package).values_list('code', flat=True)
        )
        if package.code in PACKAGE_FEATURE_MINIMUM_TIER.get('warehouse', set()) and 'warehouse' not in package_features:
            package_features.append('warehouse')
        if package.code in PACKAGE_FEATURE_MINIMUM_TIER.get('contracts', set()) and 'contracts' not in package_features:
            package_features.append('contracts')

    # Addon features
    addon_features = []
    if hasattr(tenant, 'subscription') and tenant.subscription:
        addon_features = list(
            Feature.objects.filter(addons__in=tenant.subscription.addons.all()).values_list('code', flat=True)
        )

    # Overrides
    overrides_qs = TenantFeatureOverride.objects.filter(tenant=tenant).select_related('feature')
    active_enabled_overrides = set()
    active_disabled_overrides = set()
    overrides_list = []

    for o in overrides_qs:
        is_expired = bool(o.expires_at and o.expires_at < now)
        overrides_list.append({
            'feature': o.feature.code,
            'enabled': o.enabled,
            'reason': o.reason,
            'expires_at': o.expires_at,
            'is_expired': is_expired
        })
        if not is_expired:
            if o.enabled:
                active_enabled_overrides.add(o.feature.code)
            else:
                active_disabled_overrides.add(o.feature.code)

    # Compute effective features
    base_features = set(package_features).union(set(addon_features))
    effective_features = (base_features - active_disabled_overrides).union(active_enabled_overrides)

    return {
        'effective_features': sorted(list(effective_features)),
        'package_features': package_features,
        'addon_features': addon_features,
        'overrides': overrides_list
    }


def get_tenant_entitled_features(tenant) -> list:
    """
    Shortcut returning only list of effective active feature codes.
    """
    return get_tenant_effective_features(tenant)['effective_features']


def sync_tenant_features(tenant):
    """
    Synchronizes TenantFeature rows according to the tenant's package and subscription add-ons.
    """
    subscription = Subscription.objects.filter(tenant=tenant).select_related('package').first()
    package = subscription.package if subscription else tenant.package
    if not package:
        return

    features_to_enable = set()

    # Features from package
    package_features = Feature.objects.filter(packages=package)
    for feat in package_features:
        features_to_enable.add(feat)

    for feature_code, minimum_tiers in PACKAGE_FEATURE_MINIMUM_TIER.items():
        if package.code in minimum_tiers:
            feature = Feature.objects.filter(code=feature_code).first()
            if feature:
                features_to_enable.add(feature)

    # Features from active subscription addons
    if hasattr(tenant, 'subscription') and tenant.subscription:
        addon_features = Feature.objects.filter(addons__in=tenant.subscription.addons.all())
        for feat in addon_features:
            features_to_enable.add(feat)

    # Turn off package/add-on feature rows that are no longer included. Without
    # this, removing an add-on leaves a stale enabled TenantFeature behind.
    TenantFeature.objects.filter(
        tenant=tenant,
        source__in=['PACKAGE', 'ADDON'],
    ).exclude(feature__in=features_to_enable).update(is_enabled=False)

    # Create or update TenantFeature records
    for feat in features_to_enable:
        TenantFeature.objects.update_or_create(
            tenant=tenant,
            feature=feat,
            defaults={'is_enabled': True, 'source': 'PACKAGE'}
        )

    # Invalidate cache for tenant
    for feat_code in Feature.objects.values_list('code', flat=True):
        cache.delete(f"tenant_feature_{tenant.id}_{feat_code}")


class SubscriptionUpgradeService:
    """
    Zero-downtime, transactional subscription upgrade workflow.
    Ensures that existing business data, tenant records, and vehicles remain 100% intact.
    """
    @classmethod
    def upgrade(
        cls,
        tenant,
        target_package_code: str,
        billing_cycle: str = None,
        actor=None
    ) -> dict:
        target_package = Package.objects.filter(code=target_package_code, is_active=True).first()
        if not target_package:
            from apps.subscriptions.models import PackageTier
            if target_package_code in dict(PackageTier.choices):
                target_package, _ = Package.objects.get_or_create(
                    code=target_package_code,
                    defaults={'name': f"OmniCore {target_package_code.capitalize()}", 'price_monthly': Decimal("499.00")}
                )
            else:
                raise BusinessValidationError(f"Target package '{target_package_code}' does not exist or is inactive.")


        subscription = getattr(tenant, 'subscription', None)
        if not subscription:
            raise BusinessValidationError("Tenant does not have an active subscription.")

        old_package_code = subscription.package.code
        if old_package_code == target_package_code and (not billing_cycle or billing_cycle == subscription.billing_cycle):
            raise BusinessValidationError("Tenant is already on this package and billing cycle.")

        with transaction.atomic():
            old_snapshot = {
                'package': old_package_code,
                'billing_cycle': subscription.billing_cycle,
                'status': subscription.status
            }

            # 1. Update subscription and tenant package pointer
            subscription.package = target_package
            if billing_cycle:
                subscription.billing_cycle = billing_cycle
            subscription.save(update_fields=['package', 'billing_cycle'])

            tenant.package = target_package
            tenant.save(update_fields=['package'])

            # 2. Synchronize higher-tier features
            sync_tenant_features(tenant)

            # 3. Create prorated billing invoice if upgrading
            from apps.finance.models import Invoice, InvoiceItem, InvoiceStatus
            from apps.crm.models import Customer
            now = timezone.now()
            
            # Record invoice reference for the upgrade
            upgrade_fee = target_package.price_monthly
            if upgrade_fee > 0:
                # Find or create self customer profile for billing records
                billing_customer, _ = Customer.objects.get_or_create(
                    tenant=tenant,
                    company_name=tenant.company_name,
                    defaults={'email': tenant.email, 'is_active': True}
                )
                inv = Invoice.objects.create(
                    tenant=tenant,
                    invoice_number=f"SUB-UPG-{now.strftime('%Y%m%d%H%M%S')}",
                    customer=billing_customer,
                    issue_date=now.date(),
                    due_date=now.date() + timezone.timedelta(days=7),
                    subtotal=upgrade_fee,
                    total_amount=upgrade_fee,
                    balance_due=upgrade_fee,
                    status=InvoiceStatus.ISSUED,
                    notes=f"Prorated subscription upgrade from {old_package_code} to {target_package_code}."
                )
                InvoiceItem.objects.create(
                    tenant=tenant,
                    invoice=inv,
                    description=f"Package Tier Upgrade: {target_package.name}",
                    quantity=1,
                    unit_price=upgrade_fee,
                    total_amount=upgrade_fee
                )

            # 4. Record Audit Log
            AuditService.record(
                action='PACKAGE_UPGRADED',
                actor=actor,
                tenant=tenant,
                target_type='Subscription',
                target_id=str(subscription.id),
                before_snapshot=old_snapshot,
                after_snapshot={
                    'package': target_package.code,
                    'billing_cycle': subscription.billing_cycle,
                }
            )

            entitlements = get_tenant_effective_features(tenant)

            return {
                'message': f"Subscription successfully upgraded from {old_package_code} to {target_package_code}.",
                'subscription': subscription,
                'target_package': target_package,
                'effective_features': entitlements['effective_features']
            }
