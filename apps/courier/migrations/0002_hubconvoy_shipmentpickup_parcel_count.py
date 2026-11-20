import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('courier', '0001_initial'),
        ('drivers', '0002_initial'),
        ('fleet', '0003_alter_vehicle_options'),
        ('tenants', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='shipmentpickup',
            name='parcel_count',
            field=models.PositiveIntegerField(default=1),
        ),
        migrations.AddField(
            model_name='shipmentpickup',
            name='location_name',
            field=models.CharField(blank=True, max_length=150),
        ),
        migrations.CreateModel(
            name='HubConvoy',
            fields=[
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('is_deleted', models.BooleanField(db_index=True, default=False)),
                ('deleted_at', models.DateTimeField(blank=True, null=True)),
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('convoy_number', models.CharField(db_index=True, max_length=50)),
                ('status', models.CharField(choices=[('PLANNED', 'Planned'), ('DEPARTED', 'Departed'), ('ARRIVED', 'Arrived'), ('CANCELLED', 'Cancelled')], db_index=True, default='PLANNED', max_length=20)),
                ('scheduled_departure', models.DateTimeField(blank=True, null=True)),
                ('departed_at', models.DateTimeField(blank=True, null=True)),
                ('arrived_at', models.DateTimeField(blank=True, null=True)),
                ('notes', models.TextField(blank=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(app_label)s_%(class)s_created', to=settings.AUTH_USER_MODEL)),
                ('destination_hub', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='inbound_convoys', to='courier.hub')),
                ('driver', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='courier_convoys', to='drivers.driver')),
                ('origin_hub', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='outbound_convoys', to='courier.hub')),
                ('shipments', models.ManyToManyField(related_name='courier_convoys', to='courier.shipment')),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_set', to='tenants.tenant')),
                ('vehicle', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='courier_convoys', to='fleet.vehicle')),
            ],
            options={
                'ordering': ['-created_at'],
                'unique_together': {('tenant', 'convoy_number')},
                'indexes': [models.Index(fields=['tenant', 'status'], name='courier_hub_tenant__63f1c0_idx')],
            },
        ),
    ]
