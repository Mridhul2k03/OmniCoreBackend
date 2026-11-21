import django.utils.timezone
import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='RegistrationOTP',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('registration_data', models.JSONField()),
                ('code_hash', models.CharField(max_length=128)),
                ('expires_at', models.DateTimeField()),
                ('last_sent_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('attempts', models.PositiveSmallIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='registration_otp', to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
