from django.db import migrations


def seed_reports_view_permission(apps, schema_editor):
    Permission = apps.get_model('tenants', 'Permission')
    Role = apps.get_model('tenants', 'Role')
    RolePermission = apps.get_model('tenants', 'RolePermission')
    permission, _ = Permission.objects.get_or_create(
        code='reports.view',
        defaults={'name': 'View Reports & Analytics', 'module': 'reports'},
    )
    for role_code in ('OPERATIONS_MANAGER', 'FLEET_MANAGER', 'FINANCE_USER'):
        role = Role.objects.filter(tenant__isnull=True, code=role_code).first()
        if role:
            RolePermission.objects.get_or_create(role=role, permission=permission)


class Migration(migrations.Migration):
    dependencies = [
        ('tenants', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_reports_view_permission, migrations.RunPython.noop),
    ]
