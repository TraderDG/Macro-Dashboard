"use client";
import { useQuery } from "@tanstack/react-query";
import { api, endpoints } from "@/lib/api";
import { MacroDataPoint } from "@/types";
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";
import { format } from "date-fns";

interface Props {
  country: string;
  indicator: string;
  label: string;
  color?: string;
  unit?: string;
}

export function MacroLineChart({ country, indicator, label, color = "#00d4ff", unit = "%" }: Props) {
  const { data, isLoading } = useQuery<MacroDataPoint[]>({
    queryKey: ["macro", country, indicator],
    queryFn: () => api.get(endpoints.indicators(country, indicator)).then((r) => r.data),
    refetchInterval: 60 * 60 * 1000,
    staleTime: 30 * 60 * 1000,
  });

  const chartData = (data ?? []).map((d) => ({
    date: format(new Date(d.time), "yyyy-MM"),
    value: d.value,
  }));

  const latest = chartData.at(-1);

  return (
    <div className="panel p-4 h-[220px]">
      <div className="flex items-center justify-between mb-2">
        <span className="text-terminal-muted text-[11px] uppercase tracking-wider">{label}</span>
        {latest && (
          <span className="text-terminal-text font-semibold">
            {latest.value?.toFixed(2)}{unit}
          </span>
        )}
      </div>
      {isLoading ? (
        <div className="text-terminal-muted text-center mt-8">Loading...</div>
      ) : (
        <ResponsiveContainer width="100%" height="80%">
          <AreaChart data={chartData} margin={{ top: 4, right: 4, left: -28, bottom: 0 }}>
            <defs>
              <linearGradient id={`grad-${indicator}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={color} stopOpacity={0.3} />
                <stop offset="95%" stopColor={color} stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e2d4a" />
            <XAxis dataKey="date" tick={{ fill: "#4a6080", fontSize: 10 }} tickCount={6} />
            <YAxis tick={{ fill: "#4a6080", fontSize: 10 }} tickFormatter={(v) => `${v}${unit}`} />
            <Tooltip
              contentStyle={{ background: "#0f1629", border: "1px solid #1e2d4a", borderRadius: 4 }}
              labelStyle={{ color: "#c8d6f0" }}
              formatter={(v: number) => [`${v?.toFixed(2)}${unit}`, label]}
            />
            <Area
              type="monotone" dataKey="value" stroke={color} strokeWidth={1.5}
              fill={`url(#grad-${indicator})`}
            />
          </AreaChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
