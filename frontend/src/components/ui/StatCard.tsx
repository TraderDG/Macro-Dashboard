"use client";
import { clsx } from "clsx";

interface Props {
  label: string;
  value: string | number | null;
  change?: number | null;
  unit?: string;
  subLabel?: string;
}

export function StatCard({ label, value, change, unit, subLabel }: Props) {
  const isPositive = change != null && change > 0;
  const isNegative = change != null && change < 0;

  return (
    <div className="panel p-3 flex flex-col gap-1 min-w-[140px]">
      <span className="text-terminal-muted text-[11px] uppercase tracking-wider">{label}</span>
      <div className="flex items-baseline gap-1">
        <span className="text-terminal-text text-lg font-semibold">
          {value ?? "—"}
        </span>
        {unit && <span className="text-terminal-muted text-[11px]">{unit}</span>}
      </div>
      {change != null && (
        <span className={clsx("text-[12px] font-mono", {
          "text-terminal-green": isPositive,
          "text-terminal-red": isNegative,
          "text-terminal-muted": !isPositive && !isNegative,
        })}>
          {isPositive ? "▲" : isNegative ? "▼" : "—"} {Math.abs(change).toFixed(2)}%
        </span>
      )}
      {subLabel && <span className="text-terminal-muted text-[10px]">{subLabel}</span>}
    </div>
  );
}
