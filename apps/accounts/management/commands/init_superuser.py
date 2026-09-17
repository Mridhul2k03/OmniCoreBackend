import os
from django.core.management.base import BaseCommand
from apps.accounts.models import User, PlatformRole


class Command(BaseCommand):
    help = 'Ensures the default superuser exists'

    def handle(self, *args, **options):
        email = os.environ.get('DJANGO_SUPERUSER_EMAIL', 'superadmin@omnicore.io')
        password = os.environ.get('DJANGO_SUPERUSER_PASSWORD', 'admin')

        user, created = User.objects.get_or_create(
            email=email.lower(),
            defaults={
                'username': email.lower(),
                'first_name': 'Alexander',
                'last_name': 'Vance',
                'is_staff': True,
                'is_superuser': True,
                'is_platform_admin': True,
                'platform_role': PlatformRole.SUPER_ADMIN,
            }
        )

        if created or not user.is_superuser:
            user.set_password(password)
            user.is_staff = True
            user.is_superuser = True
            user.is_platform_admin = True
            user.platform_role = PlatformRole.SUPER_ADMIN
            user.save()
            self.stdout.write(self.style.SUCCESS(f"Superuser '{email}' created successfully."))
        else:
            self.stdout.write(self.style.SUCCESS(f"Superuser '{email}' already exists."))
