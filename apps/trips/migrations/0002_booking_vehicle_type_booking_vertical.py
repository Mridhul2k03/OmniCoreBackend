from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('trips', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='booking',
            name='vehicle_type',
            field=models.CharField(db_index=True, default='heavy_truck', max_length=50),
        ),
        migrations.AddField(
            model_name='booking',
            name='vertical',
            field=models.CharField(db_index=True, default='freight_logistics', max_length=50),
        ),
    ]
