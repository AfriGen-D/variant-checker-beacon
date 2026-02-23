"""
Management command to create test users for Beacon API
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.db import IntegrityError


class Command(BaseCommand):
    help = 'Create test users for Beacon API development and testing'

    def add_arguments(self, parser):
        parser.add_argument(
            '--admin',
            action='store_true',
            help='Create an admin user',
        )
        parser.add_argument(
            '--username',
            type=str,
            default='testuser',
            help='Username for the test user',
        )
        parser.add_argument(
            '--password',
            type=str,
            default='testpass123',
            help='Password for the test user',
        )
        parser.add_argument(
            '--email',
            type=str,
            default='test@beacon.org',
            help='Email for the test user',
        )

    def handle(self, *args, **options):
        username = options['username']
        password = options['password']
        email = options['email']
        is_admin = options['admin']

        try:
            if is_admin:
                user = User.objects.create_superuser(
                    username=username,
                    email=email,
                    password=password
                )
                self.stdout.write(
                    self.style.SUCCESS(f'Successfully created admin user "{username}"')
                )
            else:
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password
                )
                self.stdout.write(
                    self.style.SUCCESS(f'Successfully created user "{username}"')
                )

            # Create some default test users if this is the first run
            if username == 'testuser':
                # Create additional test users
                test_users = [
                    {'username': 'researcher1', 'email': 'researcher1@beacon.org', 'password': 'research123'},
                    {'username': 'researcher2', 'email': 'researcher2@beacon.org', 'password': 'research123'},
                    {'username': 'admin', 'email': 'admin@beacon.org', 'password': 'admin123', 'is_staff': True},
                ]

                for user_data in test_users:
                    try:
                        is_staff = user_data.pop('is_staff', False)
                        if is_staff:
                            User.objects.create_superuser(**user_data)
                            self.stdout.write(
                                self.style.SUCCESS(f'Created admin user "{user_data["username"]}"')
                            )
                        else:
                            User.objects.create_user(**user_data)
                            self.stdout.write(
                                self.style.SUCCESS(f'Created user "{user_data["username"]}"')
                            )
                    except IntegrityError:
                        self.stdout.write(
                            self.style.WARNING(f'User "{user_data["username"]}" already exists')
                        )

                self.stdout.write(
                    self.style.SUCCESS('\nTest users created:')
                )
                self.stdout.write('  - testuser / testpass123')
                self.stdout.write('  - researcher1 / research123')
                self.stdout.write('  - researcher2 / research123')
                self.stdout.write('  - admin / admin123 (admin user)')

        except IntegrityError:
            self.stdout.write(
                self.style.ERROR(f'User "{username}" already exists')
            )