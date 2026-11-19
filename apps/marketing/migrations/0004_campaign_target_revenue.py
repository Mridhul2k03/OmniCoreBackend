from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('marketing', '0003_socialchannel_socialcampaign_socialaccount_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='campaign',
            name='vertical_target',
            field=models.CharField(blank=True, default='freight_logistics', max_length=50),
        ),
        migrations.AddField(
            model_name='campaign',
            name='attributed_revenue',
            field=models.DecimalField(decimal_places=2, default=0.0, max_digits=14),
        ),
    ]
