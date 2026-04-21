"""
Economic Calendar fetcher.
Sources:
  1. Investing.com scraper (via httpx + BeautifulSoup) — major events
  2. FRED release calendar API — official release dates
  3. Static schedule fallback for FOMC dates
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


# ─── FRED Release Calendar ────────────────────────────────────────────────────

FRED_RELEASE_IDS = {
    # release_id: (name, importance)
    "10":  ("US CPI",                  "high"),
    "50":  ("US GDP",                  "high"),
    "49":  ("US Employment (NFP)",     "high"),
    "175": ("PCE Price Index",         "high"),
    "113": ("Retail Sales",            "medium"),
    "14":  ("Industrial Production",   "medium"),
    "22":  ("Existing Home Sales",     "low"),
    "23":  ("New Home Sales",          "low"),
    "323": ("Consumer Confidence",     "medium"),
}


class FredCalendarFetcher:
    BASE = "https://api.stlouisfed.org/fred"

    def __init__(self, api_key: str):
        self.api_key = api_key

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10))
    def fetch_release_dates(self, release_id: str, days_ahead: int = 60) -> list[dict[str, Any]]:
        now = datetime.now(timezone.utc)
        end = now + timedelta(days=days_ahead)
        resp = httpx.get(
            f"{self.BASE}/release/dates",
            params={
                "release_id": release_id,
                "realtime_start": now.strftime("%Y-%m-%d"),
                "realtime_end": end.strftime("%Y-%m-%d"),
                "api_key": self.api_key,
                "file_type": "json",
            },
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json().get("release_dates", [])

    def fetch_upcoming(self, days_ahead: int = 60) -> list[dict[str, Any]]:
        events = []
        for release_id, (name, importance) in FRED_RELEASE_IDS.items():
            try:
                dates = self.fetch_release_dates(release_id, days_ahead)
                for d in dates:
                    dt_str = d.get("date", "")
                    if not dt_str:
                        continue
                    events.append({
                        "event_date": datetime.fromisoformat(dt_str).replace(tzinfo=timezone.utc),
                        "event_name": name,
                        "country": "USA",
                        "importance": importance,
                        "actual": None,
                        "forecast": None,
                        "previous": None,
                        "source": "fred",
                    })
            except Exception as e:
                logger.warning(f"FRED calendar: skip release {release_id}: {e}")
        logger.info(f"FRED calendar: {len(events)} upcoming events")
        return events


# ─── FOMC Static Schedule (authoritative — Fed publishes annually) ─────────────

class FOMCSchedule:
    """
    Hard-coded FOMC meeting dates for current year.
    Update annually from: https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm
    """
    MEETINGS_2025 = [
        "2025-01-28", "2025-01-29",
        "2025-03-18", "2025-03-19",
        "2025-05-06", "2025-05-07",
        "2025-06-17", "2025-06-18",
        "2025-07-29", "2025-07-30",
        "2025-09-16", "2025-09-17",
        "2025-10-28", "2025-10-29",
        "2025-12-09", "2025-12-10",
    ]
    MEETINGS_2026 = [
        "2026-01-27", "2026-01-28",
        "2026-03-17", "2026-03-18",
        "2026-04-28", "2026-04-29",
        "2026-06-09", "2026-06-10",
        "2026-07-28", "2026-07-29",
        "2026-09-15", "2026-09-16",
        "2026-10-27", "2026-10-28",
        "2026-12-08", "2026-12-09",
    ]

    def get_upcoming(self, days_ahead: int = 90) -> list[dict[str, Any]]:
        now = datetime.now(timezone.utc)
        cutoff = now + timedelta(days=days_ahead)
        events = []
        all_dates = self.MEETINGS_2025 + self.MEETINGS_2026
        seen_periods: set[str] = set()

        for ds in all_dates:
            dt = datetime.fromisoformat(ds).replace(tzinfo=timezone.utc)
            if dt < now or dt > cutoff:
                continue
            # Only emit the second day (decision day)
            period = ds[:7]
            if period in seen_periods:
                events.append({
                    "event_date": dt,
                    "event_name": "FOMC Rate Decision",
                    "country": "USA",
                    "importance": "high",
                    "actual": None,
                    "forecast": None,
                    "previous": None,
                    "source": "fomc_schedule",
                })
            seen_periods.add(period)

        return events


# ─── Investing.com scraper (as fallback for broader calendar) ─────────────────

class InvestingCalendarFetcher:
    """
    Scrapes investing.com economic calendar for upcoming week.
    Rate-limit friendly: only fetches once daily.
    """
    URL = "https://www.investing.com/economic-calendar/Service/getCalendarFilteredData"

    IMPORTANCE_MAP = {"1": "low", "2": "medium", "3": "high"}
    COUNTRY_MAP = {
        "5": "USA", "72": "EUR", "35": "GBR", "32": "JPN",
        "37": "CHN", "6": "CAN", "25": "AUS",
    }

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(min=3, max=15))
    def fetch_week(self) -> list[dict[str, Any]]:
        now = datetime.now(timezone.utc)
        end = now + timedelta(days=7)
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": "https://www.investing.com/economic-calendar/",
        }
        payload = {
            "country[]": list(self.COUNTRY_MAP.keys()),
            "importance[]": ["2", "3"],  # medium + high only
            "dateFrom": now.strftime("%Y-%m-%d"),
            "dateTo": end.strftime("%Y-%m-%d"),
            "timeZone": "0",
            "timeFilter": "timeRemain",
            "currentTab": "custom",
            "submitFilters": "1",
        }
        try:
            resp = httpx.post(self.URL, data=payload, headers=headers, timeout=20)
            resp.raise_for_status()
            from bs4 import BeautifulSoup

            data = resp.json()
            html = data.get("data", "")
            soup = BeautifulSoup(html, "html.parser")
            events = []
            current_date = now.date()

            for row in soup.select("tr.js-event-item"):
                try:
                    date_el = row.get("data-event-datetime", "")
                    name_el = row.select_one(".event")
                    imp_el = row.select_one("td.sentiment")
                    country_el = row.select_one("td.flagCur span")
                    actual_el = row.select_one("td.act")
                    forecast_el = row.select_one("td.fore")
                    prev_el = row.select_one("td.prev")

                    if not (date_el and name_el):
                        continue

                    dt = datetime.fromisoformat(date_el.replace(" ", "T")).replace(tzinfo=timezone.utc)
                    imp_class = imp_el.get("class", []) if imp_el else []
                    imp_num = next((c.replace("sentiment", "") for c in imp_class if "sentiment" in c), "1")

                    events.append({
                        "event_date": dt,
                        "event_name": name_el.get_text(strip=True),
                        "country": country_el.get_text(strip=True) if country_el else "USA",
                        "importance": self.IMPORTANCE_MAP.get(imp_num, "low"),
                        "actual": actual_el.get_text(strip=True) if actual_el else None,
                        "forecast": forecast_el.get_text(strip=True) if forecast_el else None,
                        "previous": prev_el.get_text(strip=True) if prev_el else None,
                        "source": "investing",
                    })
                except Exception:
                    continue

            logger.info(f"Investing calendar: {len(events)} events")
            return events
        except Exception as e:
            logger.warning(f"Investing calendar scrape failed: {e}")
            return []
