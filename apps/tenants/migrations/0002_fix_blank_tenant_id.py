import random
import string
import uuid
from django.db import migrations
from django.utils.text import slugify


def repair_blank_tenant_ids(apps, schema_editor):
    Tenant = apps.get_model('tenants', 'Tenant')
    # Find all tenants with blank or null tenant_id or slug
    for tenant in Tenant.objects.all():
        updated = False
        t_id = (tenant.tenant_id or '').strip()
        if not t_id:
            for _ in range(30):
                suffix = ''.join(random.choices(string.digits, k=6))
                candidate = f"OCT-{suffix}"
                if not Tenant.objects.filter(tenant_id=candidate).exists():
                    tenant.tenant_id = candidate
                    updated = True
                    break
            if not (tenant.tenant_id or '').strip():
                tenant.tenant_id = f"OCT-{uuid.uuid4().hex[:8].upper()}"
                updated = True

        slug_val = (tenant.slug or '').strip()
        if not slug_val:
            base_slug = slugify(tenant.company_name) if tenant.company_name else "tenant"
            if not base_slug:
                base_slug = "tenant"
            candidate = base_slug
            counter = 1
            while Tenant.objects.filter(slug=candidate).exclude(pk=tenant.pk).exists():
                candidate = f"{base_slug}-{counter}"
                counter += 1
            tenant.slug = candidate
            updated = True

        if updated:
            tenant.save()


def reverse_repair(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('tenants', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(repair_blank_tenant_ids, reverse_repair),
    ]
