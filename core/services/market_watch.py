import csv
import json
import logging
import math
import ssl
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)


MARKET_ASSETS = [
    {
        "name": "Fidelity MSCI World Index Fund",
        "symbol": "0P0001CLDK.F",
        "isin": "IE00BYX5NX33.SG",
        "color": "#1d4ed8",
    },
    {
        "name": "Vanguard Emerging Markets",
        "symbol": "0P00012I6A.F",
        "isin": "IE0031786696",
        "color": "#0ea5e9",
    },
    {
        "name": "Bitcoin",
        "symbol": "BTC-EUR",
        "isin": "N/A",
        "color": "#f7931a",
    },
    {
        "name": "Gold Futures",
        "symbol": "GC=F",
        "isin": "N/A",
        "color": "#f59e0b",
    },
]


PERIOD_CONFIG = {
    "1d": {"label": "1D", "interval": "5m", "ttl": 120, "max_points": 240},
    "5d": {"label": "1W", "interval": "30m", "ttl": 300, "max_points": 260},
    "1mo": {"label": "1M", "interval": "1d", "ttl": 900, "max_points": 280},
    "6mo": {"label": "6M", "interval": "1d", "ttl": 1800, "max_points": 300},
    "1y": {"label": "1Y", "interval": "1d", "ttl": 3600, "max_points": 320},
    "5y": {"label": "5Y", "interval": "1wk", "ttl": 7200, "max_points": 320},
    "max": {"label": "ALL", "interval": "1mo", "ttl": 10800, "max_points": 340},
}

DEFAULT_PERIOD = "1y"

CURRENCY_SYMBOLS = {
    "EUR": "€",
    "USD": "$",
    "GBP": "£",
    "JPY": "¥",
    "CHF": "CHF",
}

STOOQ_FALLBACK_MAP = {
    # Proxy equivalents used only when Yahoo is rate-limited.
    "0P0001CLDK.F": {"symbol": "swda.uk", "currency": "GBP", "is_proxy": True},
    "0P00012I6A.F": {"symbol": "eimi.uk", "currency": "GBP", "is_proxy": True},
    "BTC-EUR": {"symbol": "btceur", "currency": "EUR", "is_proxy": False},
    "GC=F": {"symbol": "xauusd", "currency": "USD", "is_proxy": True},
}

PERIOD_LOOKBACK_DAYS = {
    "1d": 2,
    "5d": 7,
    "1mo": 32,
    "6mo": 190,
    "1y": 380,
    "5y": 1900,
    "max": None,
}

YAHOO_BLOCKED_CACHE_KEY = "core.market_watch.v3.yahoo_blocked"


def normalize_period(raw_period: str) -> str:
    return raw_period if raw_period in PERIOD_CONFIG else DEFAULT_PERIOD


def period_options() -> List[Tuple[str, str]]:
    return [(value, config["label"]) for value, config in PERIOD_CONFIG.items()]


def get_market_watch_context(period: str, force_refresh: bool = False) -> Dict:
    selected_period = normalize_period(period)
    config = PERIOD_CONFIG[selected_period]
    cache_key = f"core.market_watch.v3.{selected_period}"
    backup_cache_key = f"core.market_watch.v3.backup.{selected_period}"

    if not force_refresh:
        cached_payload = cache.get(cache_key)
        if cached_payload:
            cached_payload["from_cache"] = True
            return cached_payload

    yahoo_blocked_cached = cache.get(YAHOO_BLOCKED_CACHE_KEY)
    yahoo_blocked = bool(yahoo_blocked_cached)

    charts_data, failed_assets, failed_assets_details = _fetch_all_assets(
        selected_period, config, force_stooq=yahoo_blocked
    )
    yahoo_blocked = yahoo_blocked or bool(cache.get(YAHOO_BLOCKED_CACHE_KEY))
    if not yahoo_blocked and any(
        "HTTP 429" in (item.get("reason") or "") for item in failed_assets_details
    ):
        yahoo_blocked = True
    using_stale_backup = False

    if not charts_data:
        stale_backup = cache.get(backup_cache_key)
        if stale_backup:
            charts_data = stale_backup.get("charts_data", [])
            using_stale_backup = bool(charts_data)

    payload = {
        "charts_data": charts_data,
        "failed_assets": failed_assets,
        "failed_assets_details": failed_assets_details,
        "using_stale_backup": using_stale_backup,
        "all_failed": not charts_data and bool(failed_assets),
        "yahoo_rate_limited": yahoo_blocked,
        "selected_period": selected_period,
        "selected_period_label": config["label"],
        "generated_at": timezone.localtime(),
        "from_cache": False,
    }
    cache.set(cache_key, payload, timeout=config["ttl"])
    if charts_data:
        cache.set(
            backup_cache_key,
            {
                "charts_data": charts_data,
                "generated_at": timezone.localtime(),
            },
            timeout=86400,
        )
    return payload


def _fetch_all_assets(
    period: str, period_config: Dict, force_stooq: bool = False
) -> Tuple[List[Dict], List[str], List[Dict]]:
    chart_rows: List[Tuple[int, Dict]] = []
    failed_assets: List[str] = []
    failed_assets_details: List[Dict] = []
    max_workers = min(4 if force_stooq else 2, len(MARKET_ASSETS))

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_asset = {
            executor.submit(
                _fetch_single_asset, asset, period, period_config, force_stooq
            ): (idx, asset)
            for idx, asset in enumerate(MARKET_ASSETS)
        }

        for future in as_completed(future_to_asset):
            idx, asset = future_to_asset[future]
            try:
                item, reason = future.result()
            except Exception as exc:
                item, reason = None, f"Unhandled fetch error: {type(exc).__name__}"
            if item is None:
                failed_assets.append(asset["name"])
                failed_assets_details.append(
                    {"name": asset["name"], "reason": reason or "Unknown fetch error"}
                )
                continue
            chart_rows.append((idx, item))

    chart_rows.sort(key=lambda row: row[0])
    return [row[1] for row in chart_rows], failed_assets, failed_assets_details


def _fetch_single_asset(
    asset: Dict, period: str, period_config: Dict, force_stooq: bool = False
) -> Tuple[Optional[Dict], Optional[str]]:
    if force_stooq:
        item, reason = _fetch_stooq_fallback(
            asset=asset,
            period=period,
            max_points=period_config["max_points"],
        )
        return item, reason or "Yahoo temporarily blocked (preflight)."

    attempts: List[Tuple[str, str]] = [
        (period, period_config["interval"]),
    ]

    # In intraday/week modes Yahoo sometimes returns empty series for closed markets.
    if period in {"1d", "5d"}:
        attempts.append(("1mo", "1d"))

    hosts = ("query2.finance.yahoo.com", "query1.finance.yahoo.com")
    errors: List[str] = []

    for attempt_period, attempt_interval in attempts:
        for host in hosts:
            url = (
                f"https://{host}/v8/finance/chart/{asset['symbol']}"
                f"?range={attempt_period}&interval={attempt_interval}"
            )
            try:
                payload = _open_json_url(url, timeout=6)
            except urllib.error.HTTPError as exc:
                if exc.code == 429:
                    cache.set(YAHOO_BLOCKED_CACHE_KEY, True, timeout=120)
                response_body = exc.read(220).decode("utf-8", "ignore")
                response_body = " ".join(response_body.split())
                detail = f"HTTP {exc.code}"
                if response_body:
                    detail = f"{detail}: {response_body[:120]}"
                errors.append(
                    f"{host} ({attempt_period}/{attempt_interval}): {detail}"
                )
                continue
            except Exception as exc:
                errors.append(
                    f"{host} ({attempt_period}/{attempt_interval}): {type(exc).__name__}"
                )
                continue

            parsed = _parse_chart_payload(
                asset=asset,
                payload=payload,
                period=attempt_period,
                max_points=period_config["max_points"],
            )
            if parsed is not None:
                cache.set(YAHOO_BLOCKED_CACHE_KEY, False, timeout=120)
                return parsed, None

            chart_error = ((payload.get("chart") or {}).get("error") or {})
            if chart_error:
                description = (
                    chart_error.get("description")
                    or chart_error.get("code")
                    or "Unknown chart error"
                )
                errors.append(
                    f"{host} ({attempt_period}/{attempt_interval}): {description}"
                )

    concise_error = " | ".join(errors[:3]) if errors else "No valid market payload"
    fallback_item, fallback_reason = _fetch_stooq_fallback(
        asset=asset,
        period=period,
        max_points=period_config["max_points"],
    )
    if fallback_item is not None:
        logger.warning(
            "Market Watch Yahoo failed for %s. Using Stooq fallback. Reason: %s",
            asset["symbol"],
            concise_error,
        )
        return fallback_item, fallback_reason

    logger.warning("Market Watch fetch failed for %s: %s", asset["symbol"], concise_error)
    return None, concise_error


def _parse_chart_payload(
    asset: Dict, payload: Dict, period: str, max_points: int
) -> Optional[Dict]:
    result = (payload.get("chart") or {}).get("result") or []
    if not result:
        return None

    series = result[0]
    meta = series.get("meta", {})
    timestamps = series.get("timestamp") or []
    closes = ((series.get("indicators") or {}).get("quote") or [{}])[0].get("close") or []

    valid_points = [(ts, close) for ts, close in zip(timestamps, closes) if close is not None]
    if len(valid_points) < 2:
        return None

    date_fmt = "%Y-%m-%d %H:%M" if period in {"1d", "5d"} else "%Y-%m-%d"
    labels = [datetime.fromtimestamp(ts).strftime(date_fmt) for ts, _ in valid_points]
    prices = [round(float(close), 4) for _, close in valid_points]

    first_price = prices[0]
    last_price = prices[-1]
    change_abs = last_price - first_price
    change_pct = (change_abs / first_price * 100) if first_price else 0

    labels, prices = _downsample_series(labels, prices, max_points=max_points)

    currency = meta.get("currency") or "EUR"
    currency_symbol = CURRENCY_SYMBOLS.get(currency, currency)

    symbol_safe = (
        asset["symbol"]
        .replace(".", "_")
        .replace("-", "_")
        .replace("=", "_")
        .replace("^", "_")
    )

    return {
        "id": f"chart_{symbol_safe}",
        "name": asset["name"],
        "symbol": asset["symbol"],
        "isin": asset["isin"],
        "currency": currency,
        "currency_symbol": currency_symbol,
        "current_price": round(last_price, 2),
        "change_abs": round(change_abs, 2),
        "change_pct": round(change_pct, 2),
        "high": round(max(prices), 2),
        "low": round(min(prices), 2),
        "points": len(prices),
        "labels": labels,
        "data": prices,
        "color": asset["color"],
        "is_up": change_abs >= 0,
        "source": "Yahoo Finance",
        "is_proxy": False,
    }


def _fetch_stooq_fallback(
    asset: Dict, period: str, max_points: int
) -> Tuple[Optional[Dict], Optional[str]]:
    fallback_config = STOOQ_FALLBACK_MAP.get(asset["symbol"])
    if not fallback_config:
        return None, None

    stooq_symbol = fallback_config["symbol"]
    d1, d2 = _stooq_date_window(period)
    url = f"https://stooq.com/q/d/l/?s={stooq_symbol}&i=d&d1={d1}&d2={d2}"
    try:
        text = _open_text_url(url, timeout=8)
    except Exception as exc:
        return None, f"Stooq fetch failed: {type(exc).__name__}"

    reader = csv.DictReader(text.splitlines())
    rows = []
    for row in reader:
        raw_date = (row.get("Date") or "").strip()
        raw_close = (row.get("Close") or "").strip()
        if not raw_date or not raw_close or raw_close in {"-", "No data"}:
            continue
        try:
            dt = datetime.strptime(raw_date, "%Y-%m-%d")
            close = float(raw_close)
        except (ValueError, TypeError):
            continue
        rows.append((dt, close))

    if len(rows) < 2:
        return None, "Stooq returned insufficient data points"

    rows.sort(key=lambda item: item[0])
    lookback_days = PERIOD_LOOKBACK_DAYS.get(period)
    if lookback_days:
        cutoff = datetime.now() - timedelta(days=lookback_days)
        filtered = [item for item in rows if item[0] >= cutoff]
        if len(filtered) >= 2:
            rows = filtered

    labels = [dt.strftime("%Y-%m-%d") for dt, _ in rows]
    prices = [round(close, 4) for _, close in rows]
    labels, prices = _downsample_series(labels, prices, max_points=max_points)

    first_price = prices[0]
    last_price = prices[-1]
    change_abs = last_price - first_price
    change_pct = (change_abs / first_price * 100) if first_price else 0

    currency = fallback_config["currency"]
    currency_symbol = CURRENCY_SYMBOLS.get(currency, currency)

    symbol_safe = (
        asset["symbol"]
        .replace(".", "_")
        .replace("-", "_")
        .replace("=", "_")
        .replace("^", "_")
    )

    display_name = asset["name"]
    if fallback_config.get("is_proxy"):
        display_name = f"{display_name} (Proxy)"

    item = {
        "id": f"chart_{symbol_safe}",
        "name": display_name,
        "symbol": asset["symbol"],
        "isin": asset["isin"],
        "currency": currency,
        "currency_symbol": currency_symbol,
        "current_price": round(last_price, 2),
        "change_abs": round(change_abs, 2),
        "change_pct": round(change_pct, 2),
        "high": round(max(prices), 2),
        "low": round(min(prices), 2),
        "points": len(prices),
        "labels": labels,
        "data": prices,
        "color": asset["color"],
        "is_up": change_abs >= 0,
        "source": "Stooq fallback",
        "is_proxy": fallback_config.get("is_proxy", False),
    }

    return item, "Yahoo rate-limited. Showing Stooq fallback."


def _stooq_date_window(period: str) -> Tuple[str, str]:
    now = datetime.now()
    lookback_days = PERIOD_LOOKBACK_DAYS.get(period)
    if lookback_days:
        start = now - timedelta(days=lookback_days)
    else:
        start = now - timedelta(days=365 * 20)
    return start.strftime("%Y%m%d"), now.strftime("%Y%m%d")


def _open_json_url(url: str, timeout: int = 6) -> Dict:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36"
            ),
            "Accept": "application/json,text/plain,*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://finance.yahoo.com/",
            "Origin": "https://finance.yahoo.com",
        },
    )

    retryable_codes = {500, 502, 503, 504, 999}

    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read())
        except urllib.error.HTTPError as exc:
            if exc.code in retryable_codes and attempt < 2:
                time.sleep(0.35 * (attempt + 1))
                continue
            raise
        except urllib.error.URLError as exc:
            if isinstance(exc.reason, ssl.SSLError):
                insecure_context = ssl._create_unverified_context()
                try:
                    with urllib.request.urlopen(
                        request, timeout=timeout, context=insecure_context
                    ) as response:
                        return json.loads(response.read())
                except urllib.error.HTTPError as http_exc:
                    if http_exc.code in retryable_codes and attempt < 2:
                        time.sleep(0.35 * (attempt + 1))
                        continue
                    raise
            raise

    raise urllib.error.URLError("Failed to fetch market data after retries")


def _open_text_url(url: str, timeout: int = 8) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36"
            ),
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read().decode("utf-8", "ignore")
    except urllib.error.URLError as exc:
        if isinstance(exc.reason, ssl.SSLError):
            insecure_context = ssl._create_unverified_context()
            with urllib.request.urlopen(
                request, timeout=timeout, context=insecure_context
            ) as response:
                return response.read().decode("utf-8", "ignore")
        raise


def _downsample_series(
    labels: List[str], values: List[float], max_points: int
) -> Tuple[List[str], List[float]]:
    total_points = len(values)
    if total_points <= max_points:
        return labels, values

    stride = max(1, math.ceil(total_points / max_points))
    sampled_labels = labels[::stride]
    sampled_values = values[::stride]

    if sampled_labels[-1] != labels[-1]:
        sampled_labels.append(labels[-1])
        sampled_values.append(values[-1])

    return sampled_labels, sampled_values
