from unittest.mock import patch
from datetime import date, datetime, timezone as datetime_timezone
import json
import ssl
import urllib.error

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from investments.models import Asset, AssetHistory, Transaction
from core.services import market_watch
from core.services.live_market import (
    _fetch_coinbase_market_data,
    _fetch_ft_market_data,
    _parse_ft_historical_rows,
    get_live_market_context,
    normalize_live_market_period,
    resolve_market_identity,
)
from core.services.portfolio_market import (
    get_portfolio_market_context,
    normalize_portfolio_period,
    portfolio_period_options,
)
from core.services.market_watch import (
    DEFAULT_PERIOD,
    _fetch_coingecko_fallback,
    _downsample_series,
    _fetch_stooq_fallback,
    get_market_watch_context,
    normalize_period,
)


User = get_user_model()


class MarketTransportSecurityTest(TestCase):
    @patch("core.services.market_watch.urllib.request.urlopen")
    def test_certificate_failure_is_not_retried_with_unverified_tls(self, mocked_urlopen):
        mocked_urlopen.side_effect = urllib.error.URLError(
            ssl.SSLCertVerificationError("certificate verify failed")
        )

        with self.assertRaises(urllib.error.URLError):
            market_watch._open_json_url("https://example.com/data")

        mocked_urlopen.assert_called_once()
        self.assertNotIn("context", mocked_urlopen.call_args.kwargs)


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

    @patch("core.services.market_watch._open_json_url")
    def test_coingecko_fallback_builds_crypto_chart_payload(self, mocked_open_json):
        mocked_open_json.return_value = {
            "prices": [
                [1735689600000, 90000],
                [1735776000000, 92000],
                [1735862400000, 91000],
            ]
        }
        asset = {
            "name": "Bitcoin",
            "symbol": "BTC-EUR",
            "isin": "N/A",
            "color": "#f7931a",
        }
        item, reason = _fetch_coingecko_fallback(asset, period="1mo", max_points=120)

        self.assertIsNotNone(item)
        self.assertEqual(item["source"], "CoinGecko fallback")
        self.assertEqual(item["currency"], "EUR")
        self.assertEqual(item["change_abs"], 1000)
        self.assertIn("CoinGecko", reason)

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


class PortfolioMarketServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="portfolio-user", password="pass12345")
        self.world = Asset.objects.create(
            user=self.user,
            name="ETF World",
            isin="IE00WORLD",
            category="INDEX_FUND",
            platform="Broker",
        )
        self.bitcoin = Asset.objects.create(
            user=self.user,
            name="Bitcoin",
            category="CRYPTO",
            platform="Exchange",
        )
        self.family = Asset.objects.create(
            user=self.user,
            name="Family Investments",
            category="INDEX_FUND",
            platform="Family",
            exclude_from_totals=True,
        )

        AssetHistory.objects.create(
            user=self.user,
            asset=self.world,
            date=date(2025, 1, 1),
            total_value=1000,
        )
        AssetHistory.objects.create(
            user=self.user,
            asset=self.world,
            date=date(2025, 3, 1),
            total_value=1150,
        )
        AssetHistory.objects.create(
            user=self.user,
            asset=self.world,
            date=date(2025, 4, 1),
            total_value=1300,
        )
        AssetHistory.objects.create(
            user=self.user,
            asset=self.bitcoin,
            date=date(2025, 4, 1),
            total_value=500,
        )
        AssetHistory.objects.create(
            user=self.user,
            asset=self.family,
            date=date(2025, 4, 1),
            total_value=10000,
        )
        Transaction.objects.create(
            user=self.user,
            asset=self.world,
            date=date(2025, 2, 1),
            action="BUY",
            amount=100,
        )

    def test_normalize_portfolio_period_falls_back_to_default(self):
        self.assertEqual(normalize_portfolio_period("not-real"), "1y")
        self.assertEqual(normalize_portfolio_period("3mo"), "3mo")
        self.assertIn("YTD", [item["label"] for item in portfolio_period_options()])
        self.assertNotIn("1D", [item["label"] for item in portfolio_period_options()])

    def test_selected_asset_performance_is_adjusted_for_contributions(self):
        ctx = get_portfolio_market_context(
            self.user,
            period="3mo",
            asset_id=str(self.world.id),
        )

        self.assertEqual(ctx["selected_scope"], "asset")
        self.assertEqual(ctx["selected_scope_name"], "ETF World")
        self.assertEqual(ctx["performance"]["current_value"], 1300)
        self.assertEqual(ctx["performance"]["net_contributions"], 100)
        self.assertEqual(ctx["performance"]["market_change"], 200)
        self.assertAlmostEqual(ctx["performance"]["return_pct"], 18.1818, places=3)
        self.assertEqual(ctx["chart_payload"]["market_values"], [1000.0, 1150.0, 1300.0])

    def test_asset_search_filters_portfolio_options(self):
        ctx = get_portfolio_market_context(self.user, period="1y", query="bitcoin")

        self.assertEqual([asset["name"] for asset in ctx["searchable_assets"]], ["Bitcoin"])
        self.assertEqual(ctx["query"], "bitcoin")

    def test_portfolio_scope_excludes_family_investments_when_personal_assets_exist(self):
        ctx = get_portfolio_market_context(self.user, period="all")

        self.assertEqual(ctx["selected_scope"], "portfolio")
        self.assertEqual(ctx["performance"]["current_value"], 1800)


class LiveMarketServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="live-user", password="pass12345")
        self.world = Asset.objects.create(
            user=self.user,
            name="Fidelity MSCI World Index",
            isin="IE00BYX5NX33",
            category="INDEX_FUND",
            platform="MyInvestor",
        )
        self.bitcoin = Asset.objects.create(
            user=self.user,
            name="Bitcoin",
            category="CRYPTO",
            platform="Kraken",
        )
        self.manual = Asset.objects.create(
            user=self.user,
            name="Custom ETF",
            market_symbol="CSTM.F",
            category="INDEX_FUND",
            platform="Broker",
        )
        self.gold = Asset.objects.create(
            user=self.user,
            name="Physical Gold USD",
            isin="IE00B4ND3602",
            category="COMMODITY",
            platform="Trade Republic",
        )
        self.unmapped = Asset.objects.create(
            user=self.user,
            name="Private Fund",
            category="INDEX_FUND",
            platform="Manual",
        )

    def test_live_periods_support_short_market_ranges(self):
        self.assertEqual(normalize_live_market_period("1d"), "1d")
        self.assertEqual(normalize_live_market_period("not-real"), "1y")

    def test_market_identity_resolves_known_isin_and_manual_symbol(self):
        world_identity = resolve_market_identity(self.world)
        manual_identity = resolve_market_identity(self.manual)
        bitcoin_identity = resolve_market_identity(self.bitcoin)
        gold_identity = resolve_market_identity(self.gold)

        self.assertEqual(world_identity.symbol, "0P0001CLDK.F")
        self.assertEqual(world_identity.ft_symbol_id, "667887206")
        self.assertEqual(manual_identity.symbol, "CSTM.F")
        self.assertTrue(manual_identity.is_manual)
        self.assertEqual(bitcoin_identity.symbol, "BTC-EUR")
        self.assertEqual(gold_identity.symbol, "IGLN.L")
        self.assertEqual(gold_identity.ft_symbol_id, "33139564")
        self.assertIsNone(resolve_market_identity(self.unmapped))

    @patch("core.services.live_market._fetch_live_market_asset")
    def test_live_context_fetches_selected_real_market_symbol(self, mocked_fetch):
        mocked_fetch.return_value = (
            {
                "id": "chart_0P0001CLDK_F",
                "name": "Fidelity MSCI World Index",
                "symbol": "0P0001CLDK.F",
                "isin": "IE00BYX5NX33",
                "currency": "EUR",
                "currency_symbol": "€",
                "current_price": 12.5,
                "change_abs": 1.0,
                "change_pct": 8.7,
                "high": 12.8,
                "low": 11.2,
                "points": 10,
                "labels": ["2026-01-01", "2026-01-02"],
                "data": [11.5, 12.5],
                "color": "#2563eb",
                "is_up": True,
                "source": "Yahoo Finance",
                "is_proxy": False,
                "is_stale": False,
            },
            None,
        )

        ctx = get_live_market_context(
            self.user,
            period="3mo",
            asset_id=str(self.world.id),
            force_refresh=True,
        )

        self.assertEqual(ctx["selected_asset"]["symbol"], "0P0001CLDK.F")
        self.assertEqual(ctx["chart"]["current_price"], 12.5)
        mocked_fetch.assert_called_once()
        _args, kwargs = mocked_fetch.call_args
        self.assertEqual(kwargs["asset"]["symbol"], "0P0001CLDK.F")
        self.assertEqual(kwargs["period"], "3mo")

    def test_ft_historical_parser_reads_close_prices_in_oldest_order(self):
        rows = _parse_ft_historical_rows(
            '<tr><td class="mod-ui-table__cell--text">'
            '<span class="mod-ui-hide-small-below">Wednesday, May 13, 2026</span>'
            '<span class="mod-ui-hide-medium-above">Wed, May 13, 2026</span>'
            "</td><td>13.48</td><td>13.48</td><td>13.48</td><td>13.48</td><td>0</td></tr>"
            '<tr><td class="mod-ui-table__cell--text">'
            '<span class="mod-ui-hide-small-below">Thursday, May 14, 2026</span>'
            '<span class="mod-ui-hide-medium-above">Thu, May 14, 2026</span>'
            "</td><td>13.60</td><td>13.60</td><td>13.60</td><td>13.60</td><td>0</td></tr>"
        )

        self.assertEqual(rows, [(date(2026, 5, 13), 13.48), (date(2026, 5, 14), 13.60)])

    @patch("core.services.live_market._open_text_url")
    def test_coinbase_market_data_builds_long_crypto_chart_payload(self, mocked_open_text):
        first_timestamp = int(datetime(2026, 5, 14, tzinfo=datetime_timezone.utc).timestamp())
        second_timestamp = int(datetime(2026, 5, 15, tzinfo=datetime_timezone.utc).timestamp())
        mocked_open_text.return_value = json.dumps(
            [
                [second_timestamp, 98, 103, 100, 102, 5],
                [first_timestamp, 97, 101, 99, 100, 4],
            ]
        )
        asset = {
            "name": self.bitcoin.name,
            "symbol": "BTC-EUR",
            "isin": "N/A",
            "color": "#f59e0b",
        }

        item, reason = _fetch_coinbase_market_data(asset, period="5y", max_points=120)

        self.assertIsNotNone(item)
        self.assertEqual(item["source"], "Coinbase Exchange")
        self.assertEqual(item["labels"], ["2026-05-14", "2026-05-15"])
        self.assertEqual(item["change_pct"], 2)
        self.assertIn("Coinbase", reason)

    @patch("core.services.live_market.timezone.localdate", return_value=date(2026, 5, 15))
    @patch("core.services.live_market._open_text_url")
    def test_ft_market_data_builds_chart_payload(self, mocked_open_text, _mocked_today):
        mocked_open_text.return_value = json.dumps(
            {
                "html": (
                    '<tr><td class="mod-ui-table__cell--text">'
                    '<span class="mod-ui-hide-small-below">Thursday, May 14, 2026</span>'
                    "</td><td>13.60</td><td>13.60</td><td>13.60</td><td>13.60</td><td>0</td></tr>"
                    '<tr><td class="mod-ui-table__cell--text">'
                    '<span class="mod-ui-hide-small-below">Wednesday, April 15, 2026</span>'
                    "</td><td>12.83</td><td>12.83</td><td>12.83</td><td>12.83</td><td>0</td></tr>"
                )
            }
        )
        identity = resolve_market_identity(self.world)
        asset = {
            "name": self.world.name,
            "symbol": identity.symbol,
            "isin": identity.isin,
            "color": "#2563eb",
        }

        item, reason = _fetch_ft_market_data(
            asset=asset,
            identity=identity,
            period="1mo",
            max_points=120,
        )

        self.assertIsNotNone(item)
        self.assertEqual(item["source"], "FT Markets")
        self.assertEqual(item["currency"], "EUR")
        self.assertEqual(item["labels"], ["2026-04-15", "2026-05-14"])
        self.assertEqual(item["change_pct"], 6)
        self.assertIn("FT Markets", reason)

    def test_live_context_marks_unresolved_assets(self):
        ctx = get_live_market_context(
            self.user,
            period="1y",
            asset_id=str(self.unmapped.id),
        )

        self.assertIsNone(ctx["chart"])
        self.assertIn("not mapped", ctx["fetch_error"])
        self.assertIn("Private Fund", [asset["name"] for asset in ctx["unresolved_assets"]])


class MarketWatchViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="market-user", password="pass12345")

    @patch("core.views.get_portfolio_market_context")
    def test_market_view_passes_period_asset_and_query(self, mocked_context):
        mocked_context.return_value = {
            "asset_options": [],
            "searchable_assets": [],
            "chart_payload": {},
            "performance": {
                "has_data": False,
                "has_enough_data": False,
                "is_partial": False,
                "current_value": 0,
                "market_change": 0,
                "status": "secondary",
                "return_status": "secondary",
                "return_display": "N/A",
                "net_contributions": 0,
                "transaction_count": 0,
                "start_value": 0,
                "snapshots": 0,
                "mwrr_display": "N/A",
            },
            "period_options": [{"value": "3mo", "label": "3M"}],
            "selected_period": "3mo",
            "selected_period_label": "3M",
            "selected_asset_id": "2",
            "selected_scope": "asset",
            "selected_scope_name": "ETF World",
            "selected_scope_meta": "Index Funds",
            "query": "world",
            "portfolio_has_assets": True,
            "generated_at": None,
        }

        self.client.login(username="market-user", password="pass12345")
        response = self.client.get(
            reverse("core:market_data"),
            {"period": "3mo", "asset_id": "2", "q": "world"},
        )

        self.assertEqual(response.status_code, 200)
        mocked_context.assert_called_once_with(
            user=self.user,
            period="3mo",
            asset_id="2",
            query="world",
        )

    @patch("core.views.get_live_market_context")
    def test_live_market_view_passes_period_asset_query_and_refresh(self, mocked_context):
        mocked_context.return_value = {
            "asset_options": [],
            "searchable_assets": [],
            "selected_asset": None,
            "selected_asset_id": "2",
            "chart": None,
            "fetch_error": None,
            "from_cache": False,
            "using_stale_backup": False,
            "force_refresh": True,
            "period_options": [{"value": "1d", "label": "1D"}],
            "selected_period": "1d",
            "selected_period_label": "1D",
            "query": "world",
            "resolved_count": 0,
            "unresolved_assets": [],
            "portfolio_has_assets": True,
            "yahoo_rate_limited": False,
            "generated_at": None,
        }

        self.client.login(username="market-user", password="pass12345")
        response = self.client.get(
            reverse("core:live_market_data"),
            {"period": "1d", "asset_id": "2", "q": "world", "refresh": "1"},
        )

        self.assertEqual(response.status_code, 200)
        mocked_context.assert_called_once_with(
            user=self.user,
            period="1d",
            asset_id="2",
            query="world",
            force_refresh=True,
        )
