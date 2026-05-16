import copy
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone as datetime_timezone
from html import unescape
import json
import re
from typing import Dict, Iterable, List, Optional, Tuple
from urllib.parse import urlencode

from django.core.cache import cache
from django.utils import timezone

from core.services.market_watch import (
    COINGECKO_FALLBACK_MAP,
    CURRENCY_SYMBOLS,
    PERIOD_CONFIG,
    YAHOO_BLOCKED_CACHE_KEY,
    _chart_id_for_symbol,
    _downsample_series,
    _fetch_coingecko_fallback,
    _fetch_single_asset,
    _open_text_url,
)
from investments.models import Asset
from investments.services.api import EXCLUDE_ASSET_NAME


DEFAULT_LIVE_MARKET_PERIOD = "1y"
LIVE_MARKET_PERIODS = ["1d", "5d", "1mo", "3mo", "6mo", "ytd", "1y", "5y", "max"]

CATEGORY_COLORS = {
    "CRYPTO": "#f59e0b",
    "INDEX_FUND": "#2563eb",
    "COMMODITY": "#dc2626",
    "STOCK": "#16a34a",
}

COINBASE_MARKET_IDENTITIES = {
    "BTC-EUR": {
        "product_id": "BTC-EUR",
        "currency": "EUR",
        "inception": date(2015, 4, 23),
    }
}


@dataclass(frozen=True)
class MarketIdentity:
    symbol: str
    display_name: str
    isin: str
    match_note: str
    is_manual: bool = False
    ft_symbol_id: str = ""
    ft_currency: str = ""
    ft_inception: Optional[date] = None


KNOWN_MARKET_IDENTITIES = [
    {
        "symbol": "0P0001CLDK.F",
        "display_name": "Fidelity MSCI World Index Fund P-ACC-EUR",
        "isins": {"IE00BYX5NX33"},
        "name_terms": {"fidelity", "msci", "world"},
        "match_note": "Matched Fidelity MSCI World by ISIN/name",
        "ft_symbol_id": "667887206",
        "ft_currency": "EUR",
        "ft_inception": date(2018, 3, 20),
    },
    {
        "symbol": "0P00012I6A.F",
        "display_name": "Vanguard Emerging Markets Stock Index Fund EUR Acc",
        "isins": {"IE0031786696"},
        "name_terms": {"vanguard", "emerging"},
        "match_note": "Matched Vanguard Emerging Markets by ISIN/name",
        "ft_symbol_id": "72731963",
        "ft_currency": "EUR",
        "ft_inception": date(2014, 2, 27),
    },
    {
        "symbol": "IGLN.L",
        "display_name": "iShares Physical Gold ETC",
        "isins": {"IE00B4ND3602"},
        "name_terms": {"physical", "gold"},
        "match_note": "Matched physical gold ETC by ISIN/name",
        "ft_symbol_id": "33139564",
        "ft_currency": "USD",
        "ft_inception": date(2011, 4, 11),
    },
    {
        "symbol": "BTC-EUR",
        "display_name": "Bitcoin",
        "isins": set(),
        "name_terms": {"bitcoin"},
        "match_note": "Matched Bitcoin by name",
    },
]


def normalize_live_market_period(raw_period: Optional[str]) -> str:
    return raw_period if raw_period in LIVE_MARKET_PERIODS else DEFAULT_LIVE_MARKET_PERIOD


def live_market_period_options() -> List[Dict[str, str]]:
    return [
        {"value": period, "label": PERIOD_CONFIG[period]["label"]}
        for period in LIVE_MARKET_PERIODS
    ]


def get_live_market_context(
    user,
    period: Optional[str],
    asset_id: Optional[str] = None,
    query: str = "",
    force_refresh: bool = False,
) -> Dict:
    selected_period = normalize_live_market_period(period)
    cleaned_query = (query or "").strip()
    assets = list(
        Asset.objects.filter(user=user)
        .exclude(name=EXCLUDE_ASSET_NAME)
        .order_by("name")
    )
    asset_options = _build_live_asset_options(assets)
    searchable_assets = _filter_asset_options(asset_options, cleaned_query)
    selected_option = _get_selected_option(asset_options, asset_id)

    if selected_option is None:
        selected_option = next(
            (option for option in asset_options if option["is_resolved"]),
            asset_options[0] if asset_options else None,
        )

    selected_asset_id = selected_option["id"] if selected_option else ""
    chart = None
    fetch_error = None
    from_cache = False
    using_stale_backup = False

    if selected_option and selected_option["identity"]:
        chart, fetch_error, from_cache, using_stale_backup = _get_live_chart(
            selected_option,
            selected_period,
            force_refresh=force_refresh,
        )
    elif selected_option:
        fetch_error = "This asset is not mapped to a market symbol yet."

    resolved_count = sum(1 for option in asset_options if option["is_resolved"])
    unresolved_assets = [option for option in asset_options if not option["is_resolved"]]

    return {
        "asset_options": asset_options,
        "searchable_assets": searchable_assets,
        "selected_asset": selected_option,
        "selected_asset_id": selected_asset_id,
        "chart": chart,
        "fetch_error": fetch_error,
        "from_cache": from_cache,
        "using_stale_backup": using_stale_backup,
        "force_refresh": force_refresh,
        "period_options": live_market_period_options(),
        "selected_period": selected_period,
        "selected_period_label": PERIOD_CONFIG[selected_period]["label"],
        "query": cleaned_query,
        "resolved_count": resolved_count,
        "unresolved_assets": unresolved_assets,
        "portfolio_has_assets": bool(assets),
        "yahoo_rate_limited": bool(cache.get(YAHOO_BLOCKED_CACHE_KEY)),
        "generated_at": timezone.localtime(),
    }


def resolve_market_identity(asset: Asset) -> Optional[MarketIdentity]:
    manual_symbol = (asset.market_symbol or "").strip()
    asset_isin = _normalize_isin(asset.isin)
    if manual_symbol:
        return MarketIdentity(
            symbol=manual_symbol,
            display_name=asset.name,
            isin=asset_isin or asset.isin or "N/A",
            match_note="Manual market symbol",
            is_manual=True,
        )

    asset_text = _normalize_text(" ".join([asset.name, asset.platform, asset.category]))
    for candidate in KNOWN_MARKET_IDENTITIES:
        if asset_isin and asset_isin in candidate["isins"]:
            return MarketIdentity(
                symbol=candidate["symbol"],
                display_name=candidate["display_name"],
                isin=asset_isin,
                match_note=candidate["match_note"],
                ft_symbol_id=candidate.get("ft_symbol_id", ""),
                ft_currency=candidate.get("ft_currency", ""),
                ft_inception=candidate.get("ft_inception"),
            )

        if _candidate_name_matches(candidate, asset_text):
            return MarketIdentity(
                symbol=candidate["symbol"],
                display_name=candidate["display_name"],
                isin=asset_isin or asset.isin or "N/A",
                match_note=candidate["match_note"],
                ft_symbol_id=candidate.get("ft_symbol_id", ""),
                ft_currency=candidate.get("ft_currency", ""),
                ft_inception=candidate.get("ft_inception"),
            )

    if asset.category == "CRYPTO" and "btc" in asset_text:
        return MarketIdentity(
            symbol="BTC-EUR",
            display_name="Bitcoin",
            isin=asset_isin or "N/A",
            match_note="Matched BTC crypto asset by name",
        )

    return None


def _candidate_name_matches(candidate: Dict, asset_text: str) -> bool:
    symbol = candidate["symbol"]
    if symbol == "0P0001CLDK.F":
        return "msci" in asset_text and ("world" in asset_text or "worl" in asset_text)

    terms = candidate["name_terms"]
    return bool(terms and all(term in asset_text for term in terms))


def _build_live_asset_options(assets: Iterable[Asset]) -> List[Dict]:
    options = []
    for asset in assets:
        identity = resolve_market_identity(asset)
        searchable_text = _normalize_text(
            " ".join(
                [
                    asset.name,
                    asset.platform,
                    asset.get_category_display(),
                    asset.isin or "",
                    identity.symbol if identity else "",
                    identity.display_name if identity else "",
                ]
            )
        )
        options.append(
            {
                "id": str(asset.id),
                "name": asset.name,
                "platform": asset.platform,
                "category": asset.get_category_display(),
                "category_code": asset.category,
                "isin": asset.isin or "",
                "symbol": identity.symbol if identity else "",
                "market_name": identity.display_name if identity else "",
                "match_note": identity.match_note if identity else "",
                "is_manual": bool(identity and identity.is_manual),
                "is_resolved": identity is not None,
                "identity": identity,
                "color": CATEGORY_COLORS.get(asset.category, "#2563eb"),
                "searchable_text": searchable_text,
            }
        )
    return options


def _filter_asset_options(asset_options: List[Dict], query: str) -> List[Dict]:
    if not query:
        return asset_options
    query_terms = [_normalize_text(term) for term in query.split() if term.strip()]
    if not query_terms:
        return asset_options
    return [
        asset
        for asset in asset_options
        if all(term in asset["searchable_text"] for term in query_terms)
    ]


def _get_selected_option(asset_options: List[Dict], asset_id: Optional[str]) -> Optional[Dict]:
    if not asset_id:
        return None
    return next((option for option in asset_options if option["id"] == str(asset_id)), None)


def _get_live_chart(
    selected_option: Dict,
    period: str,
    force_refresh: bool = False,
) -> tuple[Optional[Dict], Optional[str], bool, bool]:
    identity = selected_option["identity"]
    cache_key = _live_chart_cache_key(identity.symbol, period)
    backup_cache_key = _live_chart_backup_cache_key(identity.symbol, period)

    if not force_refresh:
        cached_chart = cache.get(cache_key)
        if cached_chart:
            chart = copy.deepcopy(cached_chart)
            chart["from_cache"] = True
            return chart, None, True, False

    asset_config = {
        "name": selected_option["name"],
        "symbol": identity.symbol,
        "isin": identity.isin or selected_option["isin"] or "N/A",
        "color": selected_option["color"],
    }
    force_stooq = bool(cache.get(YAHOO_BLOCKED_CACHE_KEY))
    chart, reason = _fetch_live_market_asset(
        asset=asset_config,
        identity=identity,
        period=period,
        force_stooq=force_stooq,
    )

    if chart:
        chart["portfolio_asset_name"] = selected_option["name"]
        chart["market_name"] = identity.display_name
        chart["match_note"] = identity.match_note
        chart["from_cache"] = False
        cache.set(cache_key, chart, timeout=PERIOD_CONFIG[period]["ttl"])
        cache.set(backup_cache_key, chart, timeout=86400)
        return chart, None, False, False

    backup_chart = cache.get(backup_cache_key)
    if backup_chart:
        chart = copy.deepcopy(backup_chart)
        chart["source"] = f"{chart.get('source', 'Cached data')} (cached)"
        chart["is_stale"] = True
        return chart, reason, False, True

    return None, reason or "No market data returned for this asset.", False, False


def _live_chart_cache_key(symbol: str, period: str) -> str:
    return f"core.live_market.v2.{symbol}.{period}"


def _live_chart_backup_cache_key(symbol: str, period: str) -> str:
    return f"core.live_market.v2.backup.{symbol}.{period}"


def _fetch_live_market_asset(
    asset: Dict,
    identity: MarketIdentity,
    period: str,
    force_stooq: bool = False,
) -> Tuple[Optional[Dict], Optional[str]]:
    period_config = PERIOD_CONFIG[period]

    if asset["symbol"] in COINBASE_MARKET_IDENTITIES:
        coinbase_item, coinbase_reason = _fetch_coinbase_market_data(
            asset=asset,
            period=period,
            max_points=period_config["max_points"],
        )
        if coinbase_item is not None:
            return coinbase_item, coinbase_reason

    if asset["symbol"] in COINGECKO_FALLBACK_MAP:
        crypto_item, crypto_reason = _fetch_coingecko_fallback(
            asset=asset,
            period=period,
            max_points=period_config["max_points"],
        )
        if crypto_item is not None:
            crypto_item["source"] = "CoinGecko"
            return crypto_item, crypto_reason

    if identity.ft_symbol_id:
        ft_item, ft_reason = _fetch_ft_market_data(
            asset=asset,
            identity=identity,
            period=period,
            max_points=period_config["max_points"],
        )
        if ft_item is not None:
            return ft_item, ft_reason

    return _fetch_single_asset(
        asset,
        period,
        period_config,
        force_stooq=force_stooq,
    )


def _fetch_coinbase_market_data(
    asset: Dict,
    period: str,
    max_points: int,
) -> Tuple[Optional[Dict], Optional[str]]:
    config = COINBASE_MARKET_IDENTITIES.get(asset["symbol"])
    if not config:
        return None, None

    rows_by_timestamp: Dict[int, float] = {}
    errors = []
    for start_dt, end_dt, granularity in _coinbase_windows_for_period(period, config):
        payload = {
            "granularity": granularity,
            "start": _coinbase_isoformat(start_dt),
            "end": _coinbase_isoformat(end_dt),
        }
        url = (
            f"https://api.exchange.coinbase.com/products/{config['product_id']}/candles?"
            f"{urlencode(payload)}"
        )
        try:
            response = json.loads(_open_text_url(url, timeout=8))
        except Exception as exc:
            errors.append(type(exc).__name__)
            continue

        if not isinstance(response, list):
            errors.append("unexpected response")
            continue

        for row in response:
            if not isinstance(row, list) or len(row) < 5:
                continue
            try:
                timestamp = int(row[0])
                close = float(row[4])
            except (TypeError, ValueError):
                continue
            rows_by_timestamp[timestamp] = close

    rows = sorted(rows_by_timestamp.items(), key=lambda row: row[0])
    if len(rows) < 2:
        detail = f"Coinbase fetch failed: {', '.join(errors[:2])}" if errors else None
        return None, detail or "Coinbase returned insufficient data points"

    intraday = period in {"1d", "5d"}
    date_fmt = "%Y-%m-%d %H:%M" if intraday else "%Y-%m-%d"
    labels = [
        datetime.fromtimestamp(timestamp, datetime_timezone.utc).strftime(date_fmt)
        for timestamp, _ in rows
    ]
    prices = [round(close, 4) for _, close in rows]
    first_price = prices[0]
    last_price = prices[-1]
    change_abs = last_price - first_price
    change_pct = (change_abs / first_price * 100) if first_price else 0
    high = max(prices)
    low = min(prices)
    labels, prices = _downsample_series(labels, prices, max_points=max_points)

    currency = config["currency"]
    return (
        {
            "id": _chart_id_for_symbol(asset["symbol"]),
            "name": asset["name"],
            "symbol": asset["symbol"],
            "isin": asset["isin"],
            "currency": currency,
            "currency_symbol": CURRENCY_SYMBOLS.get(currency, currency),
            "current_price": round(last_price, 2),
            "change_abs": round(change_abs, 2),
            "change_pct": round(change_pct, 2),
            "high": round(high, 2),
            "low": round(low, 2),
            "points": len(prices),
            "labels": labels,
            "data": prices,
            "color": asset["color"],
            "is_up": change_abs >= 0,
            "source": "Coinbase Exchange",
            "is_proxy": False,
            "is_stale": False,
        },
        "Showing Coinbase Exchange BTC-EUR market prices.",
    )


def _coinbase_windows_for_period(period: str, config: Dict) -> List[Tuple[datetime, datetime, int]]:
    now = timezone.now().astimezone(datetime_timezone.utc)
    today = timezone.localdate()

    if period == "1d":
        return [(now - timedelta(days=1), now, 300)]
    if period == "5d":
        return [(now - timedelta(days=7), now, 3600)]

    if period == "1mo":
        start = today - timedelta(days=35)
    elif period == "3mo":
        start = today - timedelta(days=100)
    elif period == "6mo":
        start = today - timedelta(days=190)
    elif period == "ytd":
        start = date(today.year, 1, 1)
    elif period == "1y":
        start = today - timedelta(days=365)
    elif period == "5y":
        start = today - timedelta(days=365 * 5)
    else:
        start = config.get("inception") or today - timedelta(days=365 * 10)

    start = max(start, config.get("inception") or start)
    windows = []
    cursor = start
    while cursor <= today:
        chunk_end = min(cursor + timedelta(days=299), today)
        windows.append(
            (
                datetime.combine(cursor, datetime.min.time(), tzinfo=datetime_timezone.utc),
                datetime.combine(chunk_end, datetime.min.time(), tzinfo=datetime_timezone.utc),
                86400,
            )
        )
        cursor = chunk_end + timedelta(days=1)
    return windows


def _coinbase_isoformat(value: datetime) -> str:
    return value.astimezone(datetime_timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _fetch_ft_market_data(
    asset: Dict,
    identity: MarketIdentity,
    period: str,
    max_points: int,
) -> Tuple[Optional[Dict], Optional[str]]:
    if not identity.ft_symbol_id:
        return None, None

    today = timezone.localdate()
    rows_by_date: Dict[date, float] = {}
    errors = []

    for start_date, end_date in _ft_date_windows_for_period(period, identity, today):
        payload = {
            "startDate": start_date.strftime("%Y/%m/%d"),
            "endDate": end_date.strftime("%Y/%m/%d"),
            "symbol": identity.ft_symbol_id,
        }
        url = (
            "https://markets.ft.com/data/equities/ajax/get-historical-prices?"
            f"{urlencode(payload)}"
        )
        try:
            response = json.loads(_open_text_url(url, timeout=8))
        except Exception as exc:
            errors.append(type(exc).__name__)
            continue

        for item_date, close in _parse_ft_historical_rows(response.get("html") or ""):
            rows_by_date[item_date] = close

    rows = sorted(rows_by_date.items(), key=lambda row: row[0])
    rows = _trim_ft_rows_for_period(rows, period, today)
    if len(rows) < 2:
        detail = f"FT Markets fetch failed: {', '.join(errors[:2])}" if errors else None
        return None, detail or "FT Markets returned insufficient data points"

    labels = [item_date.strftime("%Y-%m-%d") for item_date, _ in rows]
    prices = [round(close, 4) for _, close in rows]
    first_price = prices[0]
    last_price = prices[-1]
    change_abs = last_price - first_price
    change_pct = (change_abs / first_price * 100) if first_price else 0
    high = max(prices)
    low = min(prices)
    labels, prices = _downsample_series(labels, prices, max_points=max_points)

    currency = identity.ft_currency or "EUR"
    return (
        {
            "id": _chart_id_for_symbol(asset["symbol"]),
            "name": asset["name"],
            "symbol": asset["symbol"],
            "isin": asset["isin"],
            "currency": currency,
            "currency_symbol": CURRENCY_SYMBOLS.get(currency, currency),
            "current_price": round(last_price, 2),
            "change_abs": round(change_abs, 2),
            "change_pct": round(change_pct, 2),
            "high": round(high, 2),
            "low": round(low, 2),
            "points": len(prices),
            "labels": labels,
            "data": prices,
            "color": asset["color"],
            "is_up": change_abs >= 0,
            "source": "FT Markets",
            "is_proxy": False,
            "is_stale": False,
        },
        "Showing FT Markets historical market prices.",
    )


def _ft_date_windows_for_period(
    period: str,
    identity: MarketIdentity,
    today: date,
) -> List[Tuple[date, date]]:
    if period == "1d":
        start = today - timedelta(days=10)
    elif period == "5d":
        start = today - timedelta(days=14)
    elif period == "1mo":
        start = today - timedelta(days=35)
    elif period == "3mo":
        start = today - timedelta(days=100)
    elif period == "6mo":
        start = today - timedelta(days=190)
    elif period == "ytd":
        start = date(today.year, 1, 1)
    elif period == "1y":
        start = today - timedelta(days=365)
    elif period == "5y":
        start = today - timedelta(days=365 * 5)
    else:
        start = identity.ft_inception or today - timedelta(days=365 * 20)

    return _chunk_ft_date_window(max(start, identity.ft_inception or start), today)


def _chunk_ft_date_window(start: date, end: date) -> List[Tuple[date, date]]:
    windows = []
    cursor = start
    while cursor <= end:
        chunk_end = min(cursor + timedelta(days=364), end)
        windows.append((cursor, chunk_end))
        cursor = chunk_end + timedelta(days=1)
    return windows


def _trim_ft_rows_for_period(
    rows: List[Tuple[date, float]],
    period: str,
    today: date,
) -> List[Tuple[date, float]]:
    if period == "1d":
        return rows[-2:]
    if period == "5d":
        return rows[-6:]
    if period == "ytd":
        return [row for row in rows if row[0] >= date(today.year, 1, 1)]
    return rows


def _parse_ft_historical_rows(raw_html: str) -> List[Tuple[date, float]]:
    rows = []
    row_matches = re.findall(r"<tr\b[^>]*>(.*?)</tr>", raw_html or "", flags=re.IGNORECASE | re.DOTALL)
    for row_html in row_matches:
        cells = re.findall(r"<td\b[^>]*>(.*?)</td>", row_html, flags=re.IGNORECASE | re.DOTALL)
        if len(cells) < 5:
            continue

        date_text = _clean_ft_cell(cells[0])
        date_match = re.search(r"([A-Za-z]+,\s+[A-Za-z]+\s+\d{1,2},\s+\d{4})", date_text)
        if not date_match:
            continue

        try:
            item_date = datetime.strptime(date_match.group(1), "%A, %B %d, %Y").date()
            close = float(_clean_ft_cell(cells[4]).replace(",", ""))
        except (TypeError, ValueError):
            continue
        rows.append((item_date, close))
    return rows


def _clean_ft_cell(raw_value: str) -> str:
    without_tags = re.sub(r"<[^>]+>", " ", raw_value or "")
    return " ".join(unescape(without_tags).split())


def _normalize_isin(raw_isin: Optional[str]) -> str:
    value = (raw_isin or "").strip().upper()
    if not value or value == "N/A":
        return ""
    return value.split(".")[0]


def _normalize_text(value: str) -> str:
    return " ".join((value or "").casefold().replace("-", " ").replace("_", " ").split())
