from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

from core.services.user_notifications import send_new_user_signup_emails


User = get_user_model()


@receiver(post_save, sender=User, dispatch_uid="users.notify_new_user_signup")
def send_new_user_signup_notification(sender, instance, created, **kwargs):
    if created:
        send_new_user_signup_emails(instance)
