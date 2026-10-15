import uuid
from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models


class Role(models.TextChoices):
    SYSADMIN = "SYSADMIN", "System Administrator"
    IT_PRO = "IT_PRO", "IT Professional"


class CustomUserManager(UserManager):
    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault("role", Role.SYSADMIN)
        return super().create_superuser(username, email, password, **extra_fields)


class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.IT_PRO)

    objects = CustomUserManager()

    def save(self, *args, **kwargs):
        # a superuser is always a system administrator
        if self.is_superuser:
            self.role = Role.SYSADMIN
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.username} ({self.role})"
        