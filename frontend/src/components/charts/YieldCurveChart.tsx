"use client";
import { useQuery } from "@tanstack/react-query";
import { api, endpoints } from "@/lib/api";
import { YieldPoint } from "@/types";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine,
} from "recharts";

const MATURITY_ORDER = ["1m", "3m", "6m", "1y", "2y", "3y", "5y", "7y", "10y", "20y", "30y"];

export function YieldCurveChart() {
  const { data, isLoading } = useQuery<YieldPoint[]>({
    queryKey: ["yield-curve"],
    queryFn: () => api.get(endpoints.yieldCurve()).then((r) => r.data),
    refetchInterval: 15 * 60 * 1000,
  });

  const sorted = MATURITY_ORDER
    .map((m) => data?.find((d) => d.maturity === m))
    .filter(Boolean)
    .map((d) => ({ maturity: d!.maturity, yield: d!.yield_pct }));

  const isInverted = (() => {
    const y2 = sorted.find((d) => d.maturity === "2y")?.yield ?? 0;
    const y10 = sorted.find((d) => d.maturity === "10y")?.yield ?? 0;
    return y2 > y10;
  })();

  return (
    <div className="panel p-4 h-[260px]">
      <div className="flex items-center justify-between mb-3">
        <span className="text-terminal-accent text-[12px] uppercase tracking-widest font-semibold">
          US Treasury Yield Curve
        </span>
        {isInverted && (
          <span className="text-terminal-red text-[11px] border border-terminal-red px-2 py-0.5 rounded">
            ⚠ INVERTED
          </span>
        )}
      </div>
      {isLoading ? (
        <div className="text-terminal-muted text-center mt-10">Loading...</div>
      ) : (
        <ResponsiveContainer width="100%" height="85%">
          <LineChart data={sorted} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e2d4a" />
            <XAxis dataKey="maturity" tick={{ fill: "#4a6080", fontSize: 11 }} />
            <YAxis tick={{ fill: "#4a6080", fontSize: 11 }} tickFormatter={(v) => `${v}%`} />
            <Tooltip
              contentStyle={{ background: "#0f1629", border: "1px solid #1e2d4a", borderRadius: 4 }}
              labelStyle={{ color: "#c8d6f0" }}
              formatter={(v: number) => [`${v?.toFixed(3)}%`, "Yield"]}
            />
            <ReferenceLine y={0} stroke="#1e2d4a" />
            <Line
              type="monotone" dataKey="yield" stroke="#00d4ff"
              strokeWidth={2} dot={{ fill: "#00d4ff", r: 3 }} activeDot={{ r: 5 }}
            />
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
