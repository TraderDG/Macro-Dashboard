"use client";
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useWebSocket } from "@/hooks/useWebSocket";
import { clsx } from "clsx";

interface CryptoTick {
  symbol: string;
  price: number;
  change_pct: number;
  high: number;
  low: number;
  volume: number;
  time: string;
  source?: string;
}

const SYMBOL_LABELS: Record<string, string> = {
  "BTC-USD":   "Bitcoin",
  "ETH-USD":   "Ethereum",
  "BNB-USD":   "BNB",
  "SOL-USD":   "Solana",
  "XRP-USD":   "XRP",
  "ADA-USD":   "Cardano",
  "AVAX-USD":  "Avalanche",
  "DOGE-USD":  "Dogecoin",
  "LINK-USD":  "Chainlink",
  "MATIC-USD": "Polygon",
};

function formatPrice(p: number): string {
  if (p >= 1000) return p.toLocaleString("en-US", { maximumFractionDigits: 0 });
  if (p >= 1)    return p.toLocaleString("en-US", { maximumFractionDigits: 3 });
  return p.toFixed(6);
}

export function CryptoLive() {
  // Seed from REST (DB snapshot)
  const { data: restData } = useQuery<CryptoTick[]>({
    queryKey: ["crypto-live-rest"],
    queryFn: () => api.get("/api/sentiment/crypto/live").then((r) => r.data),
    refetchInterval: 30_000,
    staleTime: 10_000,
  });

  // Live overlay from Binance WebSocket
  const { data: wsTick, connected } = useWebSocket<CryptoTick>("prices");

  // Merge: REST base, WS overrides
  const [prices, setPrices] = useState<Record<string, CryptoTick>>({});
  const [flashing, setFlashing] = useState<Record<string, "up" | "down">>({});

  useEffect(() => {
    if (!restData) return;
    const map: Record<string, CryptoTick> = {};
    restData.forEach((t) => { map[t.symbol] = t; });
    setPrices(map);
  }, [restData]);

  useEffect(() => {
    if (!wsTick || wsTick.source !== "binance") return;
    const sym = wsTick.symbol;
    setPrices((prev) => {
      const prevPrice = prev[sym]?.price ?? 0;
      const direction = wsTick.price > prevPrice ? "up" : wsTick.price < prevPrice ? "down" : undefined;
      if (direction) {
        setFlashing((f) => ({ ...f, [sym]: direction }));
        setTimeout(() => setFlashing((f) => { const n = { ...f }; delete n[sym]; return n; }), 400);
      }
      return { ...prev, [sym]: wsTick };
    });
  }, [wsTick]);

  const symbols = Object.keys(SYMBOL_LABELS);
  const sorted = symbols
    .map((s) => prices[s])
    .filter(Boolean) as CryptoTick[];

  return (
    <div className="panel p-4">
      <div className="flex items-center justify-between mb-3">
        <span className="text-terminal-accent text-[12px] uppercase tracking-widest font-semibold">
          Crypto Live
        </span>
        <div className="flex items-center gap-1.5">
          <div className={clsx("w-1.5 h-1.5 rounded-full", connected ? "bg-terminal-green animate-pulse" : "bg-terminal-red")} />
          <span className="text-terminal-muted text-[10px]">{connected ? "BINANCE LIVE" : "REST ONLY"}</span>
        </div>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
        {symbols.map((sym) => {
          const tick = prices[sym];
          const flash = flashing[sym];
          return (
            <div
              key={sym}
              className={clsx(
                "bg-terminal-bg border border-terminal-border rounded p-2 transition-colors duration-300",
                flash === "up"   && "border-terminal-green/60 bg-terminal-green/5",
                flash === "down" && "border-terminal-red/60 bg-terminal-red/5",
              )}
            >
              <div className="text-terminal-muted text-[10px] truncate">{SYMBOL_LABELS[sym]}</div>
              <div className="text-terminal-text font-bold text-[13px] font-mono mt-0.5">
                {tick ? `$${formatPrice(tick.price)}` : "—"}
              </div>
              {tick && (
                <div className={clsx("text-[11px] font-mono", tick.change_pct >= 0 ? "text-terminal-green" : "text-terminal-red")}>
                  {tick.change_pct >= 0 ? "▲" : "▼"} {Math.abs(tick.change_pct).toFixed(2)}%
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
