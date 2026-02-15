from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from investments.models import Asset, AssetHistory, Transaction

User = get_user_model()


class InvestmentCSVImportViewTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="diego", password="test1234")
        self.asset = Asset.objects.create(
            user=self.user,
            name="MSCI World",
            isin="IE00XXXX",
            category="INDEX_FUND",
            platform="My Broker",
        )

    def test_import_investment_transactions_csv_creates_transactions(self):
        self.client.login(username="diego", password="test1234")
        csv_content = (
            "date,asset,action,amount,shares,price_per_share,notes\n"
            "2026-02-14,MSCI World,SELL,120.00,1,120.00,Partial sell\n"
        )
        csv_file = SimpleUploadedFile(
            "investment_transactions.csv",
            csv_content.encode("utf-8"),
            content_type="text/csv",
        )

        response = self.client.post(
            reverse("investments:import_transactions_csv"),
            {
                "csv_file": csv_file,
                "next": "/home/",
            },
        )

        self.assertRedirects(response, "/home/")
        tx = Transaction.objects.get(user=self.user, notes="Partial sell")
        self.assertEqual(tx.asset, self.asset)
        self.assertEqual(tx.date, date(2026, 2, 14))
        self.assertEqual(tx.action, "SELL")
        self.assertEqual(tx.amount, Decimal("-120.00"))

    def test_import_investment_transactions_csv_rejects_unknown_asset(self):
        self.client.login(username="diego", password="test1234")
        csv_content = (
            "date,asset,action,amount\n"
            "2026-02-14,Unknown Asset,BUY,120.00\n"
        )
        csv_file = SimpleUploadedFile(
            "investment_transactions_invalid.csv",
            csv_content.encode("utf-8"),
            content_type="text/csv",
        )

        response = self.client.post(
            reverse("investments:import_transactions_csv"),
            {"csv_file": csv_file},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "was not found")
        self.assertFalse(Transaction.objects.filter(user=self.user).exists())

    def test_import_investment_history_csv_updates_existing_snapshot(self):
        self.client.login(username="diego", password="test1234")
        AssetHistory.objects.create(
            user=self.user,
            asset=self.asset,
            date=date(2026, 2, 28),
            total_value=Decimal("15000.00"),
        )

        csv_content = (
            "date,asset,total_value\n"
            "2026-02-28,MSCI World,15420.35\n"
        )
        csv_file = SimpleUploadedFile(
            "investment_history.csv",
            csv_content.encode("utf-8"),
            content_type="text/csv",
        )

        response = self.client.post(
            reverse("investments:import_asset_history_csv"),
            {
                "csv_file": csv_file,
                "next": "/home/",
            },
        )

        self.assertRedirects(response, "/home/")
        snapshot = AssetHistory.objects.get(user=self.user, asset=self.asset, date=date(2026, 2, 28))
        self.assertEqual(snapshot.total_value, Decimal("15420.35"))
