"use client";
import { useQuery } from "@tanstack/react-query";
import { api, endpoints } from "@/lib/api";
import { MarketTicker } from "@/types";
import { clsx } from "clsx";

const TICKER_ORDER = ["^GSPC", "^NDX", "^DJI", "^N225", "^GDAXI", "^FTSE", "BTC-USD", "ETH-USD", "GC=F", "CL=F", "DX-Y.NYB", "EURUSD=X"];

export function TickerBar() {
  const { data } = useQuery<MarketTicker[]>({
    queryKey: ["market-overview"],
    queryFn: () => api.get(endpoints.marketOverview).then((r) => r.data),
    refetchInterval: 60_000,
  });

  const LABELS: Record<string, string> = {
    "^GSPC": "S&P500", "^NDX": "NDX100", "^DJI": "DJIA",
    "^N225": "NIKKEI", "^GDAXI": "DAX", "^FTSE": "FTSE100",
    "BTC-USD": "BTC", "ETH-USD": "ETH", "GC=F": "GOLD",
    "CL=F": "WTI", "DX-Y.NYB": "DXY", "EURUSD=X": "EUR/USD",
  };

  const sorted = TICKER_ORDER
    .map((sym) => data?.find((d) => d.symbol === sym))
    .filter(Boolean) as MarketTicker[];

  return (
    <div className="border-b border-terminal-border bg-terminal-panel overflow-x-auto">
      <div className="flex items-center gap-0 min-w-max">
        {sorted.map((t) => (
          <div key={t.symbol} className="flex items-center gap-2 px-4 py-2 border-r border-terminal-border hover:bg-terminal-bg cursor-pointer">
            <span className="text-terminal-muted text-[11px] uppercase">{LABELS[t.symbol] ?? t.symbol}</span>
            <span className="text-terminal-text font-semibold">
              {t.close?.toLocaleString("en-US", { maximumFractionDigits: 2 })}
            </span>
            <span className={clsx("text-[11px]", {
              "text-terminal-green": (t.change_pct ?? 0) > 0,
              "text-terminal-red": (t.change_pct ?? 0) < 0,
              "text-terminal-muted": t.change_pct == null,
            })}>
              {t.change_pct != null
                ? `${t.change_pct > 0 ? "+" : ""}${t.change_pct.toFixed(2)}%`
                : "—"}
            </span>
          </div>
        ))}
        <div className="px-4 py-2 text-terminal-muted text-[10px] italic whitespace-nowrap">
          {data ? `Updated ${new Date().toLocaleTimeString()}` : "Loading..."}
        </div>
      </div>
    </div>
  );
}
