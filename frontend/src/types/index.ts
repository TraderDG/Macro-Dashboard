export interface MarketTicker {
  symbol: string;
  asset_class: string;
  close: number;
  open: number;
  change_pct: number | null;
  time: string;
}

export interface OHLCVBar {
  time: string;
  symbol: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface YieldPoint {
  time: string;
  maturity: string;
  yield_pct: number | null;
}

export interface MacroDataPoint {
  time: string;
  country_code: string;
  indicator: string;
  value: number | null;
  unit: string | null;
  source: string;
}

export interface HeatmapEntry {
  country_code: string;
  value: number;
  time: string;
}

export interface CountryProfile {
  [indicator: string]: {
    value: number | null;
    unit: string | null;
    as_of: string;
  };
}
