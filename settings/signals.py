from django.db.models.signals import post_save
from django.contrib.auth import get_user_model
from django.dispatch import receiver
from .models import UserSettings

User = get_user_model()

@receiver(post_save, sender=User)
def create_user_settings(sender, instance, created, **kwargs):
    if created:
        UserSettings.objects.get_or_create(user=instance)

@receiver(post_save, sender=User)
def save_user_settings(sender, instance, **kwargs):
    # Usamos get_or_create por seguridad para evitar el error RelatedObjectDoesNotExist
    UserSettings.objects.get_or_create(user=instance)
    instance.settings.save()