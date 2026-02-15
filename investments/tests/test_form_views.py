from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from investments.models import Asset, AssetHistory, Transaction

User = get_user_model()


class InvestmentFormViewsTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="diego", password="test1234")
        self.other_user = User.objects.create_user(username="other", password="test1234")

        self.asset = Asset.objects.create(
            user=self.user,
            name="MSCI World",
            isin="IE00XXXX",
            category="INDEX_FUND",
            platform="My Broker",
        )
        self.other_asset = Asset.objects.create(
            user=self.other_user,
            name="BTC",
            isin="",
            category="CRYPTO",
            platform="Other Broker",
        )

    def test_create_investment_transaction_buy_stores_positive_amount(self):
        self.client.login(username="diego", password="test1234")

        response = self.client.post(
            reverse("investments:create_transaction"),
            {
                "asset": self.asset.id,
                "date": date(2026, 2, 14),
                "action": "BUY",
                "shares": "2.5",
                "price_per_share": "100.00",
                "amount": "250",
                "notes": "Monthly buy",
                "next": "/home/",
            },
        )

        self.assertRedirects(response, "/home/")
        tx = Transaction.objects.get(notes="Monthly buy")
        self.assertEqual(tx.user, self.user)
        self.assertEqual(tx.amount, Decimal("250.00"))

    def test_create_investment_transaction_sell_stores_negative_amount(self):
        self.client.login(username="diego", password="test1234")

        self.client.post(
            reverse("investments:create_transaction"),
            {
                "asset": self.asset.id,
                "date": date(2026, 2, 14),
                "action": "SELL",
                "shares": "1.0",
                "price_per_share": "120.00",
                "amount": "120",
                "notes": "Partial sell",
            },
        )

        tx = Transaction.objects.get(notes="Partial sell")
        self.assertEqual(tx.amount, Decimal("-120.00"))

    def test_create_investment_transaction_rejects_foreign_asset(self):
        self.client.login(username="diego", password="test1234")

        response = self.client.post(
            reverse("investments:create_transaction"),
            {
                "asset": self.other_asset.id,
                "date": date(2026, 2, 14),
                "action": "BUY",
                "amount": "10",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("asset", response.context["form"].errors)
        self.assertEqual(Transaction.objects.count(), 0)

    def test_create_asset_history_sets_owner_and_rejects_foreign_asset(self):
        self.client.login(username="diego", password="test1234")

        ok_response = self.client.post(
            reverse("investments:create_asset_history"),
            {
                "asset": self.asset.id,
                "date": date(2026, 2, 14),
                "total_value": "300.50",
            },
        )
        self.assertEqual(ok_response.status_code, 302)
        snap = AssetHistory.objects.get(asset=self.asset)
        self.assertEqual(snap.user, self.user)

        bad_response = self.client.post(
            reverse("investments:create_asset_history"),
            {
                "asset": self.other_asset.id,
                "date": date(2026, 2, 14),
                "total_value": "300.50",
            },
        )
        self.assertEqual(bad_response.status_code, 200)
        self.assertIn("asset", bad_response.context["form"].errors)

    def test_create_asset_name_must_be_unique_per_user_case_insensitive(self):
        self.client.login(username="diego", password="test1234")

        response = self.client.post(
            reverse("investments:create_asset"),
            {
                "name": "msci world",
                "isin": "",
                "category": "INDEX_FUND",
                "platform": "Broker",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("name", response.context["form"].errors)

        # Same name for another user is allowed
        self.client.logout()
        self.client.login(username="other", password="test1234")
        second_response = self.client.post(
            reverse("investments:create_asset"),
            {
                "name": "MSCI World",
                "isin": "",
                "category": "INDEX_FUND",
                "platform": "Other Broker",
            },
        )
        self.assertEqual(second_response.status_code, 302)
