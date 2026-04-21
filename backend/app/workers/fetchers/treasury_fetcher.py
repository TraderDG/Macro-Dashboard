"""
US Treasury yield curve fetcher — free, no API key.
Data from: https://home.treasury.gov/resource-center/data-chart-center/interest-rates
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Any

import httpx
import xml.etree.ElementTree as ET
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

TREASURY_URL = (
    "https://home.treasury.gov/resource-center/data-chart-center/"
    "interest-rates/pages/xml?data=daily_treasury_yield_curve&field_tdr_date_value_month="
)

MATURITY_MAP = {
    "d:BC_1MONTH":  "1m",
    "d:BC_2MONTH":  "2m",
    "d:BC_3MONTH":  "3m",
    "d:BC_6MONTH":  "6m",
    "d:BC_1YEAR":   "1y",
    "d:BC_2YEAR":   "2y",
    "d:BC_3YEAR":   "3y",
    "d:BC_5YEAR":   "5y",
    "d:BC_7YEAR":   "7y",
    "d:BC_10YEAR":  "10y",
    "d:BC_20YEAR":  "20y",
    "d:BC_30YEAR":  "30y",
}


class TreasuryFetcher:
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _fetch_month(self, year: int, month: int) -> list[dict[str, Any]]:
        ym = f"{year}{month:02d}"
        url = f"{TREASURY_URL}{ym}"
        resp = httpx.get(url, timeout=30)
        resp.raise_for_status()
        return self._parse_xml(resp.text)

    def _parse_xml(self, xml_text: str) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        ns = {
            "": "http://www.w3.org/2005/Atom",
            "d": "http://schemas.microsoft.com/ado/2007/08/dataservices",
            "m": "http://schemas.microsoft.com/ado/2007/08/dataservices/metadata",
        }
        try:
            root = ET.fromstring(xml_text)
            for entry in root.findall(".//m:properties", ns):
                date_el = entry.find("d:NEW_DATE", ns)
                if date_el is None or not date_el.text:
                    continue
                date_str = date_el.text[:10]
                dt = datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc)

                for xml_key, maturity in MATURITY_MAP.items():
                    tag = xml_key.split(":")[1]
                    el = entry.find(f"d:{tag}", ns)
                    if el is not None and el.text:
                        try:
                            records.append({
                                "time": dt,
                                "country_code": "USA",
                                "maturity": maturity,
                                "yield_pct": float(el.text),
                            })
                        except ValueError:
                            pass
        except ET.ParseError as e:
            logger.error(f"Treasury XML parse error: {e}")
        return records

    def fetch_range(self, months_back: int = 24) -> list[dict[str, Any]]:
        all_records: list[dict[str, Any]] = []
        now = datetime.now(timezone.utc)
        for i in range(months_back):
            target = now - timedelta(days=30 * i)
            try:
                rows = self._fetch_month(target.year, target.month)
                all_records.extend(rows)
                logger.info(f"Treasury: {target.year}-{target.month:02d} → {len(rows)} rows")
            except Exception as e:
                logger.warning(f"Treasury: skip {target.year}-{target.month}: {e}")
        return all_records

    def fetch_latest(self) -> list[dict[str, Any]]:
        now = datetime.now(timezone.utc)
        records = self._fetch_month(now.year, now.month)
        if not records:
            prev = now - timedelta(days=30)
            records = self._fetch_month(prev.year, prev.month)
        return records


class MarketFetcher:
    """Fetch daily OHLCV for key global macro assets using yfinance."""

    SYMBOLS: list[tuple[str, str]] = [
        # (yfinance_symbol, asset_class)
        ("^GSPC",  "index"),      # S&P 500
        ("^NDX",   "index"),      # Nasdaq 100
        ("^DJI",   "index"),      # Dow Jones
        ("^FTSE",  "index"),      # FTSE 100
        ("^N225",  "index"),      # Nikkei 225
        ("^HSI",   "index"),      # Hang Seng
        ("^GDAXI", "index"),      # DAX
        ("DX-Y.NYB","forex"),     # DXY Dollar Index
        ("EURUSD=X","forex"),
        ("USDJPY=X","forex"),
        ("GBPUSD=X","forex"),
        ("USDCNY=X","forex"),
        ("GC=F",   "commodity"),  # Gold
        ("CL=F",   "commodity"),  # WTI Crude Oil
        ("SI=F",   "commodity"),  # Silver
        ("HG=F",   "commodity"),  # Copper
        ("BTC-USD","crypto"),
        ("ETH-USD","crypto"),
    ]

    def fetch_daily(self, period: str = "2y") -> list[dict[str, Any]]:
        import yfinance as yf

        all_records: list[dict[str, Any]] = []
        symbols = [s for s, _ in self.SYMBOLS]
        asset_map = {s: a for s, a in self.SYMBOLS}

        try:
            data = yf.download(symbols, period=period, group_by="ticker", auto_adjust=True, progress=False)
            for symbol in symbols:
                try:
                    df = data[symbol].dropna(subset=["Close"])
                    for ts, row in df.iterrows():
                        dt = ts.to_pydatetime()
                        if dt.tzinfo is None:
                            dt = dt.replace(tzinfo=timezone.utc)
                        all_records.append({
                            "time": dt,
                            "symbol": symbol,
                            "asset_class": asset_map[symbol],
                            "open": float(row.get("Open") or 0),
                            "high": float(row.get("High") or 0),
                            "low": float(row.get("Low") or 0),
                            "close": float(row["Close"]),
                            "volume": float(row.get("Volume") or 0),
                            "source": "yfinance",
                        })
                except Exception as e:
                    logger.warning(f"MarketFetcher: skip {symbol}: {e}")
            logger.info(f"MarketFetcher: total {len(all_records)} OHLCV rows")
        except Exception as e:
            logger.error(f"MarketFetcher: batch download failed: {e}")

        return all_records

    def fetch_latest(self) -> list[dict[str, Any]]:
        return self.fetch_daily(period="5d")
