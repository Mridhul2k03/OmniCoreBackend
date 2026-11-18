from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0002_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='lead',
            name='vertical_interest',
            field=models.CharField(blank=True, default='', max_length=50),
        ),
    ]
