"""
World Bank Open Data fetcher — no API key required.
Covers 200+ countries with 1000+ macro indicators.
"""
import logging
from typing import Any

import wbgapi as wb
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

# Map: (wb_indicator_id, indicator_name, unit)
WB_INDICATORS: list[tuple[str, str, str]] = [
    ("NY.GDP.MKTP.KD.ZG", "gdp_growth",         "%"),
    ("FP.CPI.TOTL.ZG",    "cpi_yoy",             "%"),
    ("SL.UEM.TOTL.ZS",    "unemployment",        "%"),
    ("BN.CAB.XOKA.GD.ZS", "current_account_gdp", "%"),
    ("GC.DOD.TOTL.GD.ZS", "govt_debt_gdp",       "%"),
    ("NE.EXP.GNFS.ZS",    "exports_gdp",         "%"),
    ("NE.IMP.GNFS.ZS",    "imports_gdp",         "%"),
    ("NY.GDP.PCAP.CD",    "gdp_per_capita",      "USD"),
    ("SP.POP.TOTL",       "population",          "persons"),
    ("FR.INR.RINR",       "real_interest_rate",  "%"),
]

# G20 + key EM countries (ISO2)
TARGET_COUNTRIES: list[str] = [
    "US", "CN", "DE", "JP", "GB", "FR", "IN", "IT", "CA", "KR",
    "AU", "BR", "MX", "RU", "ZA", "SA", "AR", "TR", "ID", "VN",
    "TH", "MY", "SG", "PH",
]

# ISO2 → ISO3 mapping
ISO2_TO_ISO3: dict[str, str] = {
    "US": "USA", "CN": "CHN", "DE": "DEU", "JP": "JPN", "GB": "GBR",
    "FR": "FRA", "IN": "IND", "IT": "ITA", "CA": "CAN", "KR": "KOR",
    "AU": "AUS", "BR": "BRA", "MX": "MEX", "RU": "RUS", "ZA": "ZAF",
    "SA": "SAU", "AR": "ARG", "TR": "TUR", "ID": "IDN", "VN": "VNM",
    "TH": "THA", "MY": "MYS", "SG": "SGP", "PH": "PHL",
}


class WorldBankFetcher:
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=15))
    def _fetch_indicator(
        self,
        indicator_id: str,
        indicator_name: str,
        unit: str,
        start_year: int = 2000,
    ) -> list[dict[str, Any]]:
        import datetime

        records: list[dict[str, Any]] = []
        try:
            data = wb.data.DataFrame(
                indicator_id,
                economy=TARGET_COUNTRIES,
                time=range(start_year, datetime.date.today().year + 1),
                skipBlanks=True,
                labels=False,
            )
            # DataFrame has economies as columns, years as index (or vice versa)
            if data.empty:
                return records

            # Normalize: reset index, melt to long format
            data = data.reset_index()
            id_col = data.columns[0]  # "time" or "economy"

            # wbgapi returns time as rows, economies as columns
            melted = data.melt(id_vars=[id_col], var_name="economy", value_name="value")
            melted = melted.dropna(subset=["value"])

            for _, row in melted.iterrows():
                year = int(str(row[id_col]).replace("YR", ""))
                iso2 = str(row["economy"])
                iso3 = ISO2_TO_ISO3.get(iso2, iso2)

                import datetime as dt
                records.append({
                    "time": dt.datetime(year, 12, 31, tzinfo=dt.timezone.utc),
                    "country_code": iso3,
                    "indicator": indicator_name,
                    "value": float(row["value"]),
                    "unit": unit,
                    "source": "worldbank",
                })
        except Exception as e:
            logger.error(f"WorldBank: failed {indicator_id}: {e}")
        return records

    def fetch_all(self, start_year: int = 2000) -> list[dict[str, Any]]:
        all_records: list[dict[str, Any]] = []
        for wb_id, name, unit in WB_INDICATORS:
            rows = self._fetch_indicator(wb_id, name, unit, start_year)
            all_records.extend(rows)
            logger.info(f"WorldBank: {name} → {len(rows)} rows")
        return all_records

    def fetch_latest(self) -> list[dict[str, Any]]:
        """Fetch only last 3 years (annual data, no need for 30-day window)."""
        import datetime
        return self.fetch_all(start_year=datetime.date.today().year - 3)
