import axios from "axios";

// Production (behind nginx): NEXT_PUBLIC_API_URL is "" → relative URL, same-origin.
// Dev: NEXT_PUBLIC_API_URL=http://localhost:8001 → explicit cross-origin.
export const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL ?? "",
  timeout: 15000,
});

export const endpoints = {
  marketOverview: "/api/markets/overview",
  ohlcv: (symbol: string, days = 365) => `/api/markets/ohlcv/${symbol}?days=${days}`,
  byClass: (cls: string) => `/api/markets/by-class/${cls}`,
  yieldCurve: (country = "USA") => `/api/macro/yields/curve?country=${country}`,
  yieldHistory: (maturity = "10y", months = 24) =>
    `/api/macro/yields/history?maturity=${maturity}&months=${months}`,
  heatmap: (indicator = "gdp_growth") => `/api/macro/heatmap?indicator=${indicator}`,
  countryProfile: (code: string) => `/api/macro/country/${code}`,
  indicators: (country: string, indicator: string) =>
    `/api/macro/indicators?country=${country}&indicator=${indicator}`,
  ingestionStatus: "/api/macro/ingestion/status",
  health: "/health",
};
