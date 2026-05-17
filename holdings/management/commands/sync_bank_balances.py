from datetime import date

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from holdings.models import BankConnection
from holdings.services.bank_sync import BankSyncError, sync_bank_connection


class Command(BaseCommand):
    help = "Sync linked bank account balances into holding snapshots."

    def add_arguments(self, parser):
        parser.add_argument("--user", help="Username or user id to sync.")
        parser.add_argument("--connection-id", type=int, help="Specific BankConnection id.")
        parser.add_argument("--all-users", action="store_true", help="Sync every linked connection.")
        parser.add_argument("--date", help="Snapshot date in YYYY-MM-DD format.")

    def handle(self, *args, **options):
        snapshot_date = self._parse_date(options.get("date"))
        queryset = BankConnection.objects.filter(status=BankConnection.STATUS_LINKED)

        if options.get("connection_id"):
            queryset = queryset.filter(id=options["connection_id"])
        elif options.get("user"):
            queryset = queryset.filter(user=self._get_user(options["user"]))
        elif not options.get("all_users"):
            raise CommandError("Provide --connection-id, --user, or --all-users.")

        connections = list(queryset.select_related("user"))
        if not connections:
            self.stdout.write(self.style.WARNING("No linked bank connections found."))
            return

        for connection in connections:
            try:
                result = sync_bank_connection(connection, snapshot_date=snapshot_date)
            except BankSyncError as exc:
                self.stderr.write(
                    self.style.ERROR(f"{connection.id} {connection}: {exc}")
                )
                continue

            self.stdout.write(
                self.style.SUCCESS(
                    (
                        f"{connection.id} {connection}: synced {result.accounts_seen} accounts, "
                        f"{result.snapshots_created} snapshots created, "
                        f"{result.snapshots_updated} snapshots updated."
                    )
                )
            )

    def _get_user(self, value):
        User = get_user_model()
        lookup = {"id": value} if str(value).isdigit() else {"username": value}
        try:
            return User.objects.get(**lookup)
        except User.DoesNotExist as exc:
            raise CommandError(f"User not found: {value}") from exc

    def _parse_date(self, value):
        if not value:
            return None
        try:
            return date.fromisoformat(value)
        except ValueError as exc:
            raise CommandError("--date must use YYYY-MM-DD format.") from exc
