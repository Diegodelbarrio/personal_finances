from django.db.models.signals import post_save
from django.contrib.auth import get_user_model
from django.dispatch import receiver
from .models import SavingsPotentialModel, UserSettings

User = get_user_model()

@receiver(post_save, sender=User)
def create_user_settings(sender, instance, created, **kwargs):
    if created:
        user_settings, _ = UserSettings.objects.get_or_create(user=instance)
        SavingsPotentialModel.objects.get_or_create(user_settings=user_settings)

@receiver(post_save, sender=User)
def save_user_settings(sender, instance, **kwargs):
    # Usamos get_or_create por seguridad para evitar el error RelatedObjectDoesNotExist
    user_settings, _ = UserSettings.objects.get_or_create(user=instance)
    SavingsPotentialModel.objects.get_or_create(user_settings=user_settings)
    user_settings.save()
