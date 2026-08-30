from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from core.services.user_notifications import send_new_user_signup_emails


User = get_user_model()


@receiver(post_save, sender=User, dispatch_uid="users.notify_new_user_signup")
def send_new_user_signup_notification(sender, instance, created, **kwargs):
    if created:
        user_id = instance.pk

        def notify_after_commit():
            user = User.objects.filter(pk=user_id).first()
            if user is not None:
                send_new_user_signup_emails(user)

        transaction.on_commit(notify_after_commit)
