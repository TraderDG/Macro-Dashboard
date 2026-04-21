"use client";
import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, endpoints } from "@/lib/api";
import { OHLCVBar } from "@/types";
import { clsx } from "clsx";
import {
  createChart,
  CandlestickSeries,
  HistogramSeries,
  ColorType,
  CrosshairMode,
  type IChartApi,
  type Time,
} from "lightweight-charts";

const SYMBOLS = [
  { symbol: "^GSPC",    label: "S&P 500"  },
  { symbol: "^NDX",     label: "NDX 100"  },
  { symbol: "BTC-USD",  label: "Bitcoin"  },
  { symbol: "ETH-USD",  label: "Ethereum" },
  { symbol: "GC=F",     label: "Gold"     },
  { symbol: "CL=F",     label: "WTI Oil"  },
  { symbol: "DX-Y.NYB", label: "DXY"      },
  { symbol: "EURUSD=X", label: "EUR/USD"  },
];

const PERIODS = [
  { label: "1M", days: 30  },
  { label: "3M", days: 90  },
  { label: "6M", days: 180 },
  { label: "1Y", days: 365 },
  { label: "2Y", days: 730 },
];

export function CandlestickChart() {
  const [selectedSymbol, setSelectedSymbol] = useState("^GSPC");
  const [selectedDays, setSelectedDays]     = useState(365);

  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef          = useRef<IChartApi | null>(null);
  // Use any to avoid fighting lightweight-charts v5 generics
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const candleSeriesRef   = useRef<any>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const volumeSeriesRef   = useRef<any>(null);

  const { data, isLoading } = useQuery<OHLCVBar[]>({
    queryKey: ["ohlcv", selectedSymbol, selectedDays],
    queryFn: () => api.get(endpoints.ohlcv(selectedSymbol, selectedDays)).then((r) => r.data),
    staleTime: 5 * 60_000,
  });

  // ── Init chart once ──────────────────────────────────────────────────────
  useEffect(() => {
    if (!chartContainerRef.current) return;

    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: "#0a0e1a" },
        textColor: "#4a6080",
      },
      grid: {
        vertLines: { color: "#1e2d4a" },
        horzLines: { color: "#1e2d4a" },
      },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: { borderColor: "#1e2d4a" },
      timeScale: {
        borderColor: "#1e2d4a",
        timeVisible: true,
        secondsVisible: false,
      },
      width:  chartContainerRef.current.clientWidth,
      height: 320,
    });

    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor:        "#00e676",
      downColor:      "#ff1744",
      borderUpColor:  "#00e676",
      borderDownColor:"#ff1744",
      wickUpColor:    "#00e676",
      wickDownColor:  "#ff1744",
    });

    const volumeSeries = chart.addSeries(HistogramSeries, {
      color:       "#1e2d4a",
      priceFormat: { type: "volume" },
      priceScaleId:"volume",
    });
    chart.priceScale("volume").applyOptions({
      scaleMargins: { top: 0.85, bottom: 0 },
    });

    chartRef.current        = chart;
    candleSeriesRef.current = candleSeries;
    volumeSeriesRef.current = volumeSeries;

    const ro = new ResizeObserver(() => {
      if (chartContainerRef.current)
        chart.applyOptions({ width: chartContainerRef.current.clientWidth });
    });
    ro.observe(chartContainerRef.current);

    return () => {
      ro.disconnect();
      chart.remove();
    };
  }, []);

  // ── Push data on query result ────────────────────────────────────────────
  useEffect(() => {
    if (!data || !candleSeriesRef.current || !volumeSeriesRef.current) return;

    const candles = data
      .filter((d) => d.open && d.high && d.low && d.close)
      .map((d) => ({
        time:  (new Date(d.time).getTime() / 1000) as Time,
        open:  d.open,
        high:  d.high,
        low:   d.low,
        close: d.close,
      }));

    const volumes = data
      .filter((d) => d.volume != null)
      .map((d, i) => ({
        time:  (new Date(d.time).getTime() / 1000) as Time,
        value: d.volume,
        color: i > 0 && d.close >= data[i - 1].close ? "#00e67633" : "#ff174433",
      }));

    candleSeriesRef.current.setData(candles);
    volumeSeriesRef.current.setData(volumes);
    chartRef.current?.timeScale().fitContent();
  }, [data]);

  const sym        = SYMBOLS.find((s) => s.symbol === selectedSymbol);
  const latest     = data?.at(-1);
  const prev       = data?.at(-2);
  const changePct  = latest && prev && prev.close
    ? ((latest.close - prev.close) / prev.close) * 100
    : null;

  return (
    <div className="panel p-4">
      {/* Header row */}
      <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
        <div className="flex items-center gap-3">
          <span className="text-terminal-accent text-[12px] uppercase tracking-widest font-semibold">
            {sym?.label ?? selectedSymbol}
          </span>
          {latest && (
            <span className="text-terminal-text font-bold text-lg">
              {latest.close.toLocaleString("en-US", { maximumFractionDigits: 2 })}
            </span>
          )}
          {changePct != null && (
            <span className={clsx("text-[12px] font-mono",
              changePct >= 0 ? "text-terminal-green" : "text-terminal-red")}>
              {changePct >= 0 ? "▲" : "▼"} {Math.abs(changePct).toFixed(2)}%
            </span>
          )}
        </div>

        <div className="flex gap-1">
          {PERIODS.map((p) => (
            <button key={p.label} onClick={() => setSelectedDays(p.days)}
              className={clsx("px-2 py-0.5 text-[11px] border rounded transition-colors", {
                "border-terminal-accent text-terminal-accent bg-terminal-accent/10": selectedDays === p.days,
                "border-terminal-border text-terminal-muted hover:border-terminal-accent/40": selectedDays !== p.days,
              })}>
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {/* Symbol tabs */}
      <div className="flex gap-1 mb-3 flex-wrap">
        {SYMBOLS.map((s) => (
          <button key={s.symbol} onClick={() => setSelectedSymbol(s.symbol)}
            className={clsx("px-2 py-0.5 text-[11px] border rounded transition-colors", {
              "border-terminal-yellow text-terminal-yellow bg-terminal-yellow/10": selectedSymbol === s.symbol,
              "border-terminal-border text-terminal-muted hover:border-terminal-yellow/40": selectedSymbol !== s.symbol,
            })}>
            {s.label}
          </button>
        ))}
      </div>

      {/* Chart container */}
      <div className="relative">
        {isLoading && (
          <div className="absolute inset-0 flex items-center justify-center bg-terminal-bg/70 z-10 rounded">
            <span className="text-terminal-muted text-[12px]">Loading chart data...</span>
          </div>
        )}
        <div ref={chartContainerRef} />
      </div>
    </div>
  );
}
