from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from core.services.market_watch import (
    DEFAULT_PERIOD,
    _downsample_series,
    _fetch_stooq_fallback,
    get_market_watch_context,
    normalize_period,
)


User = get_user_model()


class MarketWatchServiceTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_normalize_period_falls_back_to_default(self):
        self.assertEqual(normalize_period("unknown-period"), DEFAULT_PERIOD)
        self.assertEqual(normalize_period("1mo"), "1mo")

    def test_downsample_series_reduces_points(self):
        labels = [f"2025-01-{day:02d}" for day in range(1, 201)]
        values = list(range(1, 201))

        sampled_labels, sampled_values = _downsample_series(labels, values, max_points=60)

        self.assertLessEqual(len(sampled_labels), 61)
        self.assertEqual(sampled_labels[0], labels[0])
        self.assertEqual(sampled_labels[-1], labels[-1])
        self.assertEqual(sampled_values[-1], values[-1])

    @patch("core.services.market_watch._open_text_url")
    def test_stooq_fallback_builds_chart_payload(self, mocked_open_text):
        mocked_open_text.return_value = (
            "Date,Open,High,Low,Close\n"
            "2025-01-01,90,91,89,90\n"
            "2025-01-02,90,92,89,91\n"
            "2025-01-03,91,93,90,92\n"
        )
        asset = {
            "name": "Bitcoin",
            "symbol": "BTC-EUR",
            "isin": "N/A",
            "color": "#f7931a",
        }
        item, reason = _fetch_stooq_fallback(asset, period="1mo", max_points=120)

        self.assertIsNotNone(item)
        self.assertEqual(item["source"], "Stooq fallback")
        self.assertFalse(item["is_proxy"])
        self.assertIn("Yahoo rate-limited", reason)

    @patch("core.services.market_watch._fetch_all_assets")
    def test_context_uses_cache_for_same_period(self, mocked_fetch):
        mocked_fetch.return_value = ([{"id": "chart_1"}], [], [])

        first = get_market_watch_context("1mo")
        second = get_market_watch_context("1mo")

        self.assertEqual(mocked_fetch.call_count, 1)
        mocked_fetch.assert_called_once()
        _, kwargs = mocked_fetch.call_args
        self.assertFalse(kwargs["force_stooq"])
        self.assertFalse(first["from_cache"])
        self.assertTrue(second["from_cache"])
        self.assertEqual(second["charts_data"], [{"id": "chart_1"}])

    @patch("core.services.market_watch._fetch_all_assets")
    def test_context_uses_backup_when_live_returns_empty(self, mocked_fetch):
        cache.set("core.market_watch.v3.yahoo_blocked", True, timeout=60)
        mocked_fetch.return_value = ([], ["Asset 1"], [{"name": "Asset 1", "reason": "HTTP 429"}])

        # Prime backup cache with last successful data.
        cache.set(
            "core.market_watch.v3.backup.1mo",
            {"charts_data": [{"id": "chart_backup"}]},
            timeout=300,
        )

        ctx = get_market_watch_context("1mo", force_refresh=True)
        _, kwargs = mocked_fetch.call_args
        self.assertTrue(kwargs["force_stooq"])
        self.assertTrue(ctx["using_stale_backup"])
        self.assertEqual(ctx["charts_data"], [{"id": "chart_backup"}])


class MarketWatchViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="market-user", password="pass12345")

    @patch("core.views.period_options")
    @patch("core.views.get_market_watch_context")
    def test_market_view_passes_period_and_refresh(self, mocked_context, mocked_period_options):
        mocked_context.return_value = {
            "charts_data": [],
            "failed_assets": [],
            "failed_assets_details": [],
            "using_stale_backup": False,
            "all_failed": False,
            "selected_period": "5d",
            "selected_period_label": "1W",
            "generated_at": None,
            "from_cache": False,
        }
        mocked_period_options.return_value = [("5d", "1W")]

        self.client.login(username="market-user", password="pass12345")
        response = self.client.get(reverse("core:market_data"), {"period": "5d", "refresh": "1"})

        self.assertEqual(response.status_code, 200)
        mocked_context.assert_called_once_with("5d", force_refresh=True, user=self.user)
        self.assertEqual(response.context["period_options"], [("5d", "1W")])
