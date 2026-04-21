"""
FRED (Federal Reserve Economic Data) fetcher.
Free API key: https://fred.stlouisfed.org/docs/api/api_key.html
"""
import logging
from datetime import datetime, timezone
from typing import Any

import pandas as pd
from fredapi import Fred
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings

logger = logging.getLogger(__name__)

# Map: (series_id, country_code, indicator_name, unit)
FRED_SERIES: list[tuple[str, str, str, str]] = [
    # USA
    ("GDP",          "USA", "gdp_nominal",     "USD_bn"),
    ("A191RL1Q225SBEA", "USA", "gdp_growth",   "%"),
    ("CPIAUCSL",     "USA", "cpi_index",        "index"),
    ("T10YIE",       "USA", "inflation_exp_10y","%"),
    ("UNRATE",       "USA", "unemployment",     "%"),
    ("FEDFUNDS",     "USA", "fed_funds_rate",   "%"),
    ("DGS2",         "USA", "treasury_2y",      "%"),
    ("DGS10",        "USA", "treasury_10y",     "%"),
    ("DGS30",        "USA", "treasury_30y",     "%"),
    ("T10Y2Y",       "USA", "yield_spread_10y2y","%"),
    ("VIXCLS",       "USA", "vix",              "index"),
    ("DTWEXBGS",     "USA", "dxy_broad",        "index"),
    ("BAMLH0A0HYM2", "USA", "hy_spread",        "%"),
    ("DCOILWTICO",   "USA", "oil_wti",          "USD"),
    ("GOLDAMGBD228NLBM", "USA", "gold_price",   "USD"),
    ("USREC",        "USA", "recession_flag",   "binary"),
    # Euro Area
    ("ECBDFR",       "EUR", "ecb_deposit_rate", "%"),
    ("HICP",         "EUR", "cpi_hicp",         "index"),
]


class FredFetcher:
    def __init__(self):
        if not settings.FRED_API_KEY:
            raise RuntimeError(
                "FRED_API_KEY not set — get a free key at "
                "https://fred.stlouisfed.org/docs/api/api_key.html and add it to .env"
            )
        self.fred = Fred(api_key=settings.FRED_API_KEY)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def fetch_series(self, series_id: str, start: str = "2000-01-01") -> pd.DataFrame:
        data = self.fred.get_series(series_id, observation_start=start)
        df = data.dropna().reset_index()
        df.columns = ["date", "value"]
        df["date"] = pd.to_datetime(df["date"]).dt.tz_localize("UTC")
        return df

    def fetch_all(self, start: str = "2000-01-01") -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for series_id, country_code, indicator, unit in FRED_SERIES:
            try:
                df = self.fetch_series(series_id, start)
                for _, row in df.iterrows():
                    records.append({
                        "time": row["date"].to_pydatetime(),
                        "country_code": country_code,
                        "indicator": indicator,
                        "value": float(row["value"]),
                        "unit": unit,
                        "source": "fred",
                    })
                logger.info(f"FRED: fetched {len(df)} rows for {series_id}")
            except Exception as e:
                logger.error(f"FRED: failed to fetch {series_id}: {e}")
        return records

    def fetch_latest(self) -> list[dict[str, Any]]:
        """Fetch only the last 30 days for scheduled updates."""
        from datetime import timedelta
        start = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")
        return self.fetch_all(start=start)
