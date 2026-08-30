from django.core import mail
from django.test import TestCase, override_settings

from core.services.email_delivery import send_marketing_email, send_transactional_email


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    EMAIL_MARKETING_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    EMAIL_MARKETING_ENABLED=True,
    EMAIL_SUBJECT_PREFIX="[FinOrbit]",
    EMAIL_TRANSACTIONAL_FROM_EMAIL="tx@finorbit.test",
    EMAIL_TRANSACTIONAL_REPLY_TO=["support@finorbit.test"],
    EMAIL_MARKETING_FROM_EMAIL="news@finorbit.test",
    EMAIL_MARKETING_REPLY_TO=["newsletter@finorbit.test"],
    EMAIL_MARKETING_BATCH_SIZE=2,
)
class EmailDeliveryServiceTest(TestCase):
    def test_send_transactional_email(self):
        result = send_transactional_email(
            subject="Verification email",
            to=["user@example.com"],
            text_body="Test body",
        )

        self.assertEqual(result.messages_sent, 1)
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.subject, "[FinOrbit] Verification email")
        self.assertEqual(message.from_email, "tx@finorbit.test")
        self.assertEqual(message.reply_to, ["support@finorbit.test"])
        self.assertEqual(message.to, ["user@example.com"])

    def test_send_marketing_email_batches_recipients(self):
        recipients = ["a@example.com", "b@example.com", "c@example.com"]
        result = send_marketing_email(
            subject="Newsletter #1",
            recipients=recipients,
            text_body="Campaign body",
        )

        self.assertEqual(result.messages_sent, 2)
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(mail.outbox[0].to, [])
        self.assertEqual(mail.outbox[1].to, [])
        self.assertEqual(mail.outbox[0].bcc, ["a@example.com", "b@example.com"])
        self.assertEqual(mail.outbox[1].bcc, ["c@example.com"])
        self.assertEqual(mail.outbox[0].from_email, "news@finorbit.test")
        self.assertEqual(mail.outbox[0].reply_to, ["newsletter@finorbit.test"])
