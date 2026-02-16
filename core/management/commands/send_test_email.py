from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

from core.services.email_delivery import send_marketing_email, send_transactional_email


class Command(BaseCommand):
    help = "Sends a test email using the configured delivery infrastructure."

    def add_arguments(self, parser):
        parser.add_argument("--to", required=True, help="Recipient email address.")
        parser.add_argument(
            "--category",
            choices=["transactional", "marketing"],
            default="transactional",
            help="Email category to test.",
        )
        parser.add_argument(
            "--subject",
            default="Email infrastructure test",
            help="Subject line for the test email.",
        )

    def handle(self, *args, **options):
        to = options["to"].strip()
        category = options["category"]
        subject = options["subject"]

        if not to:
            raise CommandError("--to cannot be empty.")

        if category == "marketing":
            if not settings.EMAIL_MARKETING_ENABLED:
                raise CommandError(
                    "Marketing channel disabled. Set EMAIL_MARKETING_ENABLED=True."
                )
            result = send_marketing_email(
                subject=subject,
                recipients=[to],
                text_body=(
                    "Hello,\n\n"
                    "This is a marketing delivery test from FinOrbit.\n"
                    "If you received this, the marketing email channel is configured."
                ),
                html_body=(
                    "<p>Hello,</p>"
                    "<p>This is a <strong>marketing delivery test</strong> from FinOrbit.</p>"
                    "<p>If you received this, the marketing email channel is configured.</p>"
                ),
            )
        else:
            result = send_transactional_email(
                subject=subject,
                to=[to],
                text_body=(
                    "Hello,\n\n"
                    "This is a transactional delivery test from FinOrbit.\n"
                    "If you received this, your transactional email channel is configured."
                ),
                html_body=(
                    "<p>Hello,</p>"
                    "<p>This is a <strong>transactional delivery test</strong> from FinOrbit.</p>"
                    "<p>If you received this, your transactional email channel is configured.</p>"
                ),
            )

        self.stdout.write(
            self.style.SUCCESS(
                (
                    f"Email sent: category={result.category}, "
                    f"messages={result.messages_sent}, recipients={result.recipients}, "
                    f"backend={result.backend}"
                )
            )
        )
