"use client";
import { useQuery } from "@tanstack/react-query";
import { api, endpoints } from "@/lib/api";
import { MarketTicker } from "@/types";
import { clsx } from "clsx";

const ASSET_CLASSES = [
  { id: "index",     label: "Indices" },
  { id: "forex",     label: "FX" },
  { id: "commodity", label: "Commodities" },
  { id: "crypto",    label: "Crypto" },
];

function ClassTable({ assetClass, label }: { assetClass: string; label: string }) {
  const { data } = useQuery<MarketTicker[]>({
    queryKey: ["market-class", assetClass],
    queryFn: () => api.get(endpoints.byClass(assetClass)).then((r) => r.data),
    refetchInterval: 60_000,
  });

  return (
    <div className="panel p-3">
      <div className="text-terminal-accent text-[11px] uppercase tracking-widest mb-2">{label}</div>
      <table className="w-full text-[12px]">
        <thead>
          <tr className="text-terminal-muted text-[10px]">
            <th className="text-left pb-1">Symbol</th>
            <th className="text-right pb-1">Price</th>
            <th className="text-right pb-1">Chg%</th>
          </tr>
        </thead>
        <tbody>
          {(data ?? []).map((t) => (
            <tr key={t.symbol} className="border-t border-terminal-border/50 hover:bg-terminal-bg">
              <td className="py-1 text-terminal-text font-mono">{t.symbol}</td>
              <td className="py-1 text-right text-terminal-text">
                {t.close?.toLocaleString("en-US", { maximumFractionDigits: 4 })}
              </td>
              <td className={clsx("py-1 text-right", {
                "text-terminal-green": (t.change_pct ?? 0) > 0,
                "text-terminal-red": (t.change_pct ?? 0) < 0,
                "text-terminal-muted": t.change_pct == null,
              })}>
                {t.change_pct != null ? `${t.change_pct > 0 ? "+" : ""}${t.change_pct.toFixed(2)}%` : "—"}
              </td>
            </tr>
          ))}
          {!data && (
            <tr><td colSpan={3} className="text-terminal-muted text-center py-3">Loading...</td></tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

export function MarketGrid() {
  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
      {ASSET_CLASSES.map((ac) => (
        <ClassTable key={ac.id} assetClass={ac.id} label={ac.label} />
      ))}
    </div>
  );
}
