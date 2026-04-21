"use client";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { formatDistanceToNow } from "date-fns";
import { clsx } from "clsx";

interface NewsItem {
  title: string;
  url: string | null;
  source: string | null;
  published_at: string | null;
}

const SOURCE_COLORS: Record<string, string> = {
  "Reuters":           "text-[#ff6b35]",
  "Bloomberg":         "text-terminal-accent",
  "Financial Times":   "text-[#ff0099]",
  "Wall Street Journal": "text-blue-400",
  "CNBC":              "text-[#00a86b]",
};

function timeAgo(dateStr: string | null): string {
  if (!dateStr) return "";
  try {
    return formatDistanceToNow(new Date(dateStr), { addSuffix: true });
  } catch {
    return "";
  }
}

export function NewsFeed() {
  const { data, isLoading, dataUpdatedAt } = useQuery<NewsItem[]>({
    queryKey: ["news-feed"],
    queryFn: () => api.get("/api/sentiment/news?limit=20").then((r) => r.data),
    refetchInterval: 5 * 60_000,
    staleTime: 2 * 60_000,
  });

  return (
    <div className="panel p-4 h-full flex flex-col">
      <div className="flex items-center justify-between mb-3">
        <span className="text-terminal-accent text-[12px] uppercase tracking-widest font-semibold">
          Market News
        </span>
        {dataUpdatedAt > 0 && (
          <span className="text-terminal-muted text-[10px]">
            {timeAgo(new Date(dataUpdatedAt).toISOString())}
          </span>
        )}
      </div>

      {isLoading && (
        <div className="text-terminal-muted text-[12px] py-4 text-center">Loading headlines...</div>
      )}

      <div className="flex flex-col divide-y divide-terminal-border overflow-y-auto flex-1 max-h-[400px]">
        {(data ?? []).map((item, i) => {
          const sourceColor = SOURCE_COLORS[item.source ?? ""] ?? "text-terminal-muted";
          return (
            <div key={i} className="py-2 hover:bg-terminal-bg/50 transition-colors px-1 rounded">
              {item.url ? (
                <a
                  href={item.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-terminal-text text-[12px] leading-snug hover:text-terminal-accent transition-colors line-clamp-2"
                >
                  {item.title}
                </a>
              ) : (
                <p className="text-terminal-text text-[12px] leading-snug line-clamp-2">
                  {item.title}
                </p>
              )}
              <div className="flex items-center gap-2 mt-1">
                {item.source && (
                  <span className={clsx("text-[10px] font-semibold", sourceColor)}>
                    {item.source}
                  </span>
                )}
                {item.published_at && (
                  <span className="text-terminal-muted text-[10px]">
                    {timeAgo(item.published_at)}
                  </span>
                )}
              </div>
            </div>
          );
        })}
        {!isLoading && (!data || data.length === 0) && (
          <div className="text-terminal-muted text-[12px] py-4 text-center">No headlines yet</div>
        )}
      </div>
    </div>
  );
}
