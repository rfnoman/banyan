from django.core.management.base import BaseCommand
from django.contrib.auth.models import User

USERS = [
    {"username": "admin", "email": "admin@banyantree.com", "password": "password", "is_staff": True, "is_superuser": True},
    {"username": "alice", "email": "alice@banyantree.com", "password": "password"},
    {"username": "bob", "email": "bob@banyantree.com", "password": "password"},
]


class Command(BaseCommand):
    help = "Seed 3 team users into PostgreSQL auth"

    def handle(self, *args, **options):
        for u in USERS:
            is_staff = u.pop("is_staff", False)
            is_superuser = u.pop("is_superuser", False)
            password = u.pop("password")
            user, created = User.objects.get_or_create(username=u["username"], defaults=u)
            if created:
                user.set_password(password)
                user.is_staff = is_staff
                user.is_superuser = is_superuser
                user.save()
                self.stdout.write(self.style.SUCCESS(f"Created user: {user.username}"))
            else:
                self.stdout.write(f"User already exists: {user.username}")
