from django.db import models
from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    avatar = models.FileField(
        upload_to="avatars/",
        blank=True,
        null=True,
        help_text="Upload a profile image.",
    )
