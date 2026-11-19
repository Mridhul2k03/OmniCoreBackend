from django.db import migrations


def add_marketing_view_permission(apps, schema_editor):
    Permission = apps.get_model('tenants', 'Permission')
    Role = apps.get_model('tenants', 'Role')
    RolePermission = apps.get_model('tenants', 'RolePermission')

    permission, _ = Permission.objects.get_or_create(
        code='marketing.view',
        defaults={'name': 'View Marketing Campaigns', 'module': 'marketing'},
    )
    sales_role = Role.objects.filter(tenant__isnull=True, code='SALES_CRM_USER').first()
    if sales_role:
        RolePermission.objects.get_or_create(role=sales_role, permission=permission)


class Migration(migrations.Migration):
    dependencies = [
        ('marketing', '0004_campaign_target_revenue'),
        ('tenants', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(add_marketing_view_permission, migrations.RunPython.noop),
    ]
