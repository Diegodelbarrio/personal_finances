from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings


User = get_user_model()


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    EMAIL_SUBJECT_PREFIX="[FinOrbit]",
    EMAIL_TRANSACTIONAL_FROM_EMAIL="tx@finorbit.test",
    EMAIL_TRANSACTIONAL_REPLY_TO=["support@finorbit.test"],
    NEW_USER_NOTIFICATION_ENABLED=True,
    NEW_USER_NOTIFICATION_RECIPIENTS=["admin@finorbit.test"],
    NEW_USER_WELCOME_EMAIL_ENABLED=True,
    SITE_URL="https://finorbit.test",
)
class NewUserNotificationTest(TestCase):
    def test_new_user_creation_sends_welcome_and_admin_notification_emails(self):
        with self.captureOnCommitCallbacks(execute=True):
            user = User.objects.create_user(
                username="new-investor",
                email="investor@example.com",
                password="testpass123",
                first_name="New",
                last_name="Investor",
            )

        self.assertEqual(len(mail.outbox), 2)

        welcome_email = mail.outbox[0]
        self.assertEqual(welcome_email.to, ["investor@example.com"])
        self.assertEqual(welcome_email.from_email, "tx@finorbit.test")
        self.assertEqual(welcome_email.reply_to, ["support@finorbit.test"])
        self.assertIn("Welcome to FinOrbit", welcome_email.subject)
        self.assertIn("Your account has been created successfully.", welcome_email.body)
        self.assertIn("https://finorbit.test/accounts/login/", welcome_email.body)

        admin_email = mail.outbox[1]
        self.assertEqual(admin_email.to, ["admin@finorbit.test"])
        self.assertEqual(admin_email.from_email, "tx@finorbit.test")
        self.assertEqual(admin_email.reply_to, ["support@finorbit.test"])
        self.assertIn("New user registered: new-investor", admin_email.subject)
        self.assertIn("investor@example.com", admin_email.body)
        self.assertIn(f"https://finorbit.test/admin/users/user/{user.pk}/change/", admin_email.body)


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    NEW_USER_NOTIFICATION_ENABLED=False,
    NEW_USER_WELCOME_EMAIL_ENABLED=False,
    NEW_USER_NOTIFICATION_RECIPIENTS=["admin@finorbit.test"],
)
class DisabledNewUserNotificationTest(TestCase):
    def test_disabled_notification_does_not_send_email(self):
        User.objects.create_user(
            username="quiet-user",
            email="quiet@example.com",
            password="testpass123",
        )

        self.assertEqual(len(mail.outbox), 0)
