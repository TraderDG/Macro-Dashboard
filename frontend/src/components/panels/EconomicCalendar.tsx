"use client";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { clsx } from "clsx";
import { format, isToday, isTomorrow } from "date-fns";

interface CalendarEvent {
  id: number;
  event_date: string;
  event_name: string;
  country: string;
  importance: "low" | "medium" | "high";
  actual: string | null;
  forecast: string | null;
  previous: string | null;
  is_past: boolean;
}

const IMPORTANCE_STYLES = {
  high:   { dot: "bg-terminal-red",    text: "text-terminal-red"   },
  medium: { dot: "bg-terminal-yellow", text: "text-terminal-yellow"},
  low:    { dot: "bg-terminal-muted",  text: "text-terminal-muted" },
};

const COUNTRY_FLAG: Record<string, string> = {
  USA: "🇺🇸", EUR: "🇪🇺", GBR: "🇬🇧", JPN: "🇯🇵",
  CHN: "🇨🇳", CAN: "🇨🇦", AUS: "🇦🇺", DEU: "🇩🇪",
};

function DateLabel({ dateStr }: { dateStr: string }) {
  const d = new Date(dateStr);
  if (isToday(d))    return <span className="text-terminal-accent font-bold">TODAY</span>;
  if (isTomorrow(d)) return <span className="text-terminal-yellow">TOMORROW</span>;
  return <span className="text-terminal-muted">{format(d, "EEE dd MMM")}</span>;
}

export function EconomicCalendar() {
  const { data, isLoading } = useQuery<CalendarEvent[]>({
    queryKey: ["economic-calendar"],
    queryFn: () => api.get("/api/sentiment/calendar?days_ahead=14&days_behind=3").then((r) => r.data),
    refetchInterval: 15 * 60_000,
    staleTime: 5 * 60_000,
  });

  // Group by date
  const grouped: Record<string, CalendarEvent[]> = {};
  (data ?? []).forEach((ev) => {
    const dateKey = ev.event_date.slice(0, 10);
    if (!grouped[dateKey]) grouped[dateKey] = [];
    grouped[dateKey].push(ev);
  });

  const sortedDates = Object.keys(grouped).sort();

  return (
    <div className="panel p-4 h-full">
      <div className="flex items-center justify-between mb-3">
        <span className="text-terminal-accent text-[12px] uppercase tracking-widest font-semibold">
          Economic Calendar
        </span>
        <span className="text-terminal-muted text-[10px]">Next 14 days</span>
      </div>

      {isLoading && (
        <div className="text-terminal-muted text-center py-8 text-[12px]">Loading events...</div>
      )}

      {!isLoading && sortedDates.length === 0 && (
        <div className="text-terminal-muted text-center py-8 text-[12px]">No events found</div>
      )}

      <div className="space-y-3 overflow-y-auto max-h-[420px] pr-1">
        {sortedDates.map((dateKey) => {
          const events = grouped[dateKey];
          const hasHighImportance = events.some((e) => e.importance === "high");
          return (
            <div key={dateKey}>
              {/* Date header */}
              <div className={clsx(
                "flex items-center gap-2 py-1 border-b mb-1",
                hasHighImportance ? "border-terminal-red/30" : "border-terminal-border",
              )}>
                <span className="text-[11px]">
                  <DateLabel dateStr={`${dateKey}T00:00:00Z`} />
                </span>
                <span className="text-terminal-muted text-[10px]">
                  {format(new Date(dateKey), "yyyy")}
                </span>
                {hasHighImportance && (
                  <span className="ml-auto text-terminal-red text-[10px] border border-terminal-red/40 px-1 rounded">
                    HIGH IMPACT
                  </span>
                )}
              </div>

              {/* Events */}
              {events.map((ev) => {
                const imp = IMPORTANCE_STYLES[ev.importance];
                const isPastEv = ev.is_past;
                return (
                  <div
                    key={ev.id}
                    className={clsx(
                      "flex items-center gap-2 py-1.5 px-1 rounded text-[12px] hover:bg-terminal-bg/50 transition-colors",
                      isPastEv && "opacity-50",
                    )}
                  >
                    {/* Importance dot */}
                    <span className={clsx("w-1.5 h-1.5 rounded-full flex-shrink-0", imp.dot)} />

                    {/* Time */}
                    <span className="text-terminal-muted text-[10px] w-10 flex-shrink-0">
                      {format(new Date(ev.event_date), "HH:mm")}
                    </span>

                    {/* Country */}
                    <span className="text-[12px] w-5 flex-shrink-0">
                      {COUNTRY_FLAG[ev.country] ?? ev.country}
                    </span>

                    {/* Event name */}
                    <span className={clsx("flex-1 truncate", imp.text, "font-medium")}>
                      {ev.event_name}
                    </span>

                    {/* Actual / Forecast / Previous */}
                    <div className="flex gap-2 flex-shrink-0 text-[11px] font-mono">
                      {ev.actual && (
                        <span className="text-terminal-green font-bold">{ev.actual}</span>
                      )}
                      {ev.forecast && !ev.actual && (
                        <span className="text-terminal-muted">est. {ev.forecast}</span>
                      )}
                      {ev.previous && (
                        <span className="text-terminal-muted">prev {ev.previous}</span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          );
        })}
      </div>
    </div>
  );
}
