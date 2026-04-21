"use client";
import { useQuery } from "@tanstack/react-query";
import { api, endpoints } from "@/lib/api";
import { useEffect, useRef } from "react";

interface FearGreedData {
  score: number | null;
  label: string | null;
  time: string | null;
}

interface HistoryPoint {
  time: string;
  score: number;
  label: string;
}

// SVG arc-based gauge — no extra dependency
function Gauge({ score }: { score: number }) {
  const pct = Math.max(0, Math.min(100, score)) / 100;

  // Color: 0=red → 50=yellow → 100=green
  const hue = Math.round(pct * 120); // 0→red, 60→yellow, 120→green
  const color = `hsl(${hue}, 90%, 50%)`;

  // Arc math (semicircle: -180° to 0°)
  const cx = 80, cy = 80, r = 60;
  const startAngle = Math.PI;         // left
  const endAngle = 0;                 // right
  const angle = startAngle + pct * (endAngle - startAngle); // reversed: 0→π, 100→0
  const needleAngle = Math.PI - pct * Math.PI;

  const arcX = (a: number) => cx + r * Math.cos(a);
  const arcY = (a: number) => cy + r * Math.sin(a);

  // Background arc (gray)
  const bgPath = `M ${arcX(Math.PI)} ${arcY(Math.PI)} A ${r} ${r} 0 0 1 ${arcX(0)} ${arcY(0)}`;
  // Filled arc
  const filledPath = `M ${arcX(Math.PI)} ${arcY(Math.PI)} A ${r} ${r} 0 ${pct > 0.5 ? 0 : 1} 1 ${arcX(needleAngle)} ${arcY(needleAngle)}`;

  // Needle
  const nLen = 48;
  const nx = cx + nLen * Math.cos(needleAngle);
  const ny = cy + nLen * Math.sin(needleAngle);

  return (
    <svg viewBox="0 0 160 90" className="w-full max-w-[180px]">
      {/* Zone labels */}
      <text x="6"  y="86" fill="#ff1744" fontSize="8" textAnchor="middle">Fear</text>
      <text x="154" y="86" fill="#00e676" fontSize="8" textAnchor="middle">Greed</text>

      {/* Background track */}
      <path d={bgPath} fill="none" stroke="#1e2d4a" strokeWidth="12" strokeLinecap="round" />

      {/* Colored fill */}
      {pct > 0 && (
        <path d={filledPath} fill="none" stroke={color} strokeWidth="12" strokeLinecap="round" />
      )}

      {/* Needle */}
      <line x1={cx} y1={cy} x2={nx} y2={ny} stroke="#c8d6f0" strokeWidth="2" strokeLinecap="round" />
      <circle cx={cx} cy={cy} r="4" fill="#c8d6f0" />

      {/* Score */}
      <text x={cx} y={cy - 16} fill={color} fontSize="20" fontWeight="bold" textAnchor="middle" fontFamily="monospace">
        {Math.round(score)}
      </text>
    </svg>
  );
}

const ZONE_COLORS: Record<string, string> = {
  "Extreme Fear": "text-red-500",
  "Fear":         "text-orange-400",
  "Neutral":      "text-yellow-400",
  "Greed":        "text-green-400",
  "Extreme Greed":"text-emerald-400",
};

export function FearGreedGauge() {
  const { data } = useQuery<FearGreedData>({
    queryKey: ["fear-greed-latest"],
    queryFn: () => api.get("/api/sentiment/fear-greed/latest").then((r) => r.data),
    refetchInterval: 4 * 60 * 60 * 1000,
    staleTime: 30 * 60 * 1000,
  });

  const { data: history } = useQuery<HistoryPoint[]>({
    queryKey: ["fear-greed-history"],
    queryFn: () => api.get("/api/sentiment/fear-greed/history?days=30").then((r) => r.data),
    staleTime: 60 * 60 * 1000,
  });

  const score = data?.score ?? 50;
  const label = data?.label ?? "Neutral";
  const labelColor = ZONE_COLORS[label] ?? "text-terminal-text";

  const prev7 = history?.at(-8);
  const prev30 = history?.[0];
  const trend7 = prev7 ? score - (prev7.score ?? 0) : null;
  const trend30 = prev30 ? score - (prev30.score ?? 0) : null;

  return (
    <div className="panel p-4 flex flex-col items-center gap-2">
      <span className="text-terminal-accent text-[12px] uppercase tracking-widest font-semibold self-start">
        Fear &amp; Greed Index
      </span>

      <Gauge score={score} />

      <span className={`text-[14px] font-bold ${labelColor}`}>{label}</span>

      {/* 7d / 30d comparison */}
      <div className="flex gap-4 w-full justify-center mt-1">
        {[{ label: "7d ago", val: trend7 }, { label: "30d ago", val: trend30 }].map(({ label: l, val }) => (
          <div key={l} className="flex flex-col items-center">
            <span className="text-terminal-muted text-[10px]">{l}</span>
            <span className={`text-[12px] font-mono ${val == null ? "text-terminal-muted" : val >= 0 ? "text-terminal-green" : "text-terminal-red"}`}>
              {val == null ? "—" : `${val >= 0 ? "+" : ""}${val.toFixed(0)}`}
            </span>
          </div>
        ))}
      </div>

      {data?.time && (
        <span className="text-terminal-muted text-[10px]">
          Updated {new Date(data.time).toLocaleDateString()}
        </span>
      )}
    </div>
  );
}
