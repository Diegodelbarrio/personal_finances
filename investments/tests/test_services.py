from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from investments.models import Asset, AssetHistory, Transaction
from investments.services.api import (
    get_annual_portfolio_evolution,
    get_investment_detailed_evolution,
    get_family_investment_performance,
    get_portfolio_overview,
)
from investments.services.history import (
    get_allocation_chart,
    get_monthly_contributions_bar,
    get_performance_history,
)

User = get_user_model()


class InvestmentsServiceTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username="test", password="1234")

        self.asset = Asset.objects.create(
            user=self.user,
            name="ETF World",
            category="INDEX_FUND",
            platform="Test Broker",
        )

        AssetHistory.objects.create(
            user=self.user,
            asset=self.asset,
            date=date(2024, 1, 31),
            total_value=5000,
        )

    def test_portfolio_overview(self):
        data = get_portfolio_overview(self.user)

        self.assertEqual(data["global_current_value"], 5000)
        self.assertIsNotNone(data["last_market_date"])

    def test_performance_history_uses_latest_snapshot_and_carries_it_forward(self):
        Transaction.objects.create(
            user=self.user,
            asset=self.asset,
            date=date(2024, 1, 5),
            action="BUY",
            amount=1000,
        )
        Transaction.objects.create(
            user=self.user,
            asset=self.asset,
            date=date(2024, 2, 5),
            action="BUY",
            amount=500,
        )
        AssetHistory.objects.create(
            user=self.user,
            asset=self.asset,
            date=date(2024, 1, 10),
            total_value=4500,
        )
        AssetHistory.objects.create(
            user=self.user,
            asset=self.asset,
            date=date(2024, 3, 31),
            total_value=6000,
        )

        history = get_performance_history(self.user)

        self.assertEqual([item["label"] for item in history], ["Jan 24", "Feb 24", "Mar 24"])
        self.assertEqual([item["invested"] for item in history], [1000, 1500, 1500])
        self.assertEqual([item["market"] for item in history], [5000, 5000, 6000])

    def test_investment_records_reject_cross_user_ownership(self):
        other_user = User.objects.create_user(username="other", password="1234")

        with self.assertRaises(ValidationError):
            Transaction.objects.create(
                user=other_user,
                asset=self.asset,
                date=date(2024, 2, 1),
                action="BUY",
                amount=10,
            )

        with self.assertRaises(ValidationError):
            AssetHistory.objects.create(
                user=other_user,
                asset=self.asset,
                date=date(2024, 2, 1),
                total_value=10,
            )

    def test_asset_history_rejects_duplicate_asset_and_date(self):
        with self.assertRaises(ValidationError):
            AssetHistory.objects.create(
                user=self.user,
                asset=self.asset,
                date=date(2024, 1, 31),
                total_value=5100,
            )

    @patch("investments.services.api.timezone.localdate", return_value=date(2024, 3, 15))
    def test_annual_series_uses_opening_snapshot_and_post_snapshot_contributions(
        self, _localdate
    ):
        Transaction.objects.create(
            user=self.user,
            asset=self.asset,
            date=date(2024, 2, 10),
            action="BUY",
            amount=500,
        )
        AssetHistory.objects.create(
            user=self.user,
            asset=self.asset,
            date=date(2024, 3, 10),
            total_value=6000,
        )

        with self.assertNumQueries(3):
            portfolio = get_annual_portfolio_evolution(self.user, 2024)
        with self.assertNumQueries(3):
            detailed = get_investment_detailed_evolution(self.user, 2024)

        self.assertEqual([month["market_value"] for month in portfolio], [5000, 5500, 6000])
        self.assertEqual([month["contributions"] for month in portfolio], [0, 500, 0])
        self.assertEqual([month["profit_loss"] for month in portfolio], [0, 0, 500])
        self.assertEqual(detailed["assets"][0]["annual_profit"], 500)
        self.assertEqual(detailed["assets"][0]["annual_contributions"], 500)

    def test_portfolio_overview_has_constant_query_count(self):
        with self.assertNumQueries(3):
            data = get_portfolio_overview(self.user)

        self.assertEqual(data["global_current_value"], 5000)

    def test_personal_asset_count_uses_exclusion_flag(self):
        Asset.objects.create(
            user=self.user,
            name="Externally managed assets",
            category="OTHER",
            platform="Test",
            exclude_from_totals=True,
        )

        data = get_portfolio_overview(self.user)

        self.assertEqual(len(data["portfolio"]), 2)
        self.assertEqual(data["personal_asset_count"], 1)

    def test_family_asset_is_global_but_excluded_from_personal_charts(self):
        Transaction.objects.create(
            user=self.user,
            asset=self.asset,
            date=date(2024, 1, 5),
            action="BUY",
            amount=1000,
        )
        family_asset = Asset.objects.create(
            user=self.user,
            name="Family Investments",
            category="INDEX_FUND",
            platform="Family Broker",
            exclude_from_totals=True,
        )
        Transaction.objects.create(
            user=self.user,
            asset=family_asset,
            date=date(2024, 1, 5),
            action="BUY",
            amount=10000,
        )
        AssetHistory.objects.create(
            user=self.user,
            asset=family_asset,
            date=date(2024, 1, 31),
            total_value=12000,
        )

        overview = get_portfolio_overview(self.user)
        allocation_labels, allocation_data = get_allocation_chart(
            overview["chart_assets"]
        )
        performance = get_performance_history(self.user)
        contribution_labels, contribution_datasets = get_monthly_contributions_bar(
            self.user
        )

        self.assertEqual(overview["global_current_value"], 17000)
        self.assertEqual(overview["no_family_value"], 5000)
        self.assertEqual(overview["personal_asset_count"], 1)
        self.assertEqual(allocation_labels, ["ETF World"])
        self.assertEqual(allocation_data, [5000.0])
        self.assertEqual(performance[0]["invested"], 1000)
        self.assertEqual(performance[0]["market"], 5000)
        self.assertEqual(contribution_labels, ["Jan 24"])
        self.assertEqual(
            contribution_datasets,
            [{"label": "ETF World", "data": [1000.0]}],
        )

    def test_excluded_asset_performance_aggregates_all_excluded_assets(self):
        first = Asset.objects.create(
            user=self.user,
            name="Externally managed one",
            category="OTHER",
            platform="Test",
            exclude_from_totals=True,
        )
        second = Asset.objects.create(
            user=self.user,
            name="Externally managed two",
            category="OTHER",
            platform="Test",
            exclude_from_totals=True,
        )
        for asset, opening, contribution, closing in (
            (first, 1000, 100, 1200),
            (second, 500, 50, 600),
        ):
            AssetHistory.objects.create(
                user=self.user,
                asset=asset,
                date=date(2023, 12, 31),
                total_value=opening,
            )
            Transaction.objects.create(
                user=self.user,
                asset=asset,
                date=date(2024, 2, 1),
                action="BUY",
                amount=contribution,
            )
            AssetHistory.objects.create(
                user=self.user,
                asset=asset,
                date=date(2024, 12, 31),
                total_value=closing,
            )

        with self.assertNumQueries(3):
            data = get_family_investment_performance(self.user, 2024)

        self.assertEqual(data["name"], "Excluded assets")
        self.assertEqual(data["current_value"], 1800)
        self.assertEqual(data["profit"], 150)
