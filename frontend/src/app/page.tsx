"use client";
import { useState } from "react";
import { clsx } from "clsx";

// Phase 1
import { TickerBar }      from "@/components/panels/TickerBar";
import { YieldCurveChart } from "@/components/charts/YieldCurveChart";
import { MacroLineChart }  from "@/components/charts/MacroLineChart";
import { CountryPanel }    from "@/components/panels/CountryPanel";
import { MarketGrid }      from "@/components/panels/MarketGrid";

// Phase 2
import { CandlestickChart }  from "@/components/charts/CandlestickChart";
import { FearGreedGauge }    from "@/components/panels/FearGreedGauge";
import { EconomicCalendar }  from "@/components/panels/EconomicCalendar";
import { CryptoLive }        from "@/components/panels/CryptoLive";
import { NewsFeed }          from "@/components/panels/NewsFeed";
import { useWebSocket }      from "@/hooks/useWebSocket";

// ─── Nav tabs ────────────────────────────────────────────────────────────────
const TABS = [
  { id: "overview",  label: "Overview"   },
  { id: "charts",    label: "Charts"     },
  { id: "macro",     label: "Macro"      },
  { id: "sentiment", label: "Sentiment"  },
  { id: "calendar",  label: "Calendar"   },
] as const;
type TabId = typeof TABS[number]["id"];

// ─── Header ───────────────────────────────────────────────────────────────────
function Header({ wsConnected, activeTab, onTab }: {
  wsConnected: boolean;
  activeTab: TabId;
  onTab: (t: TabId) => void;
}) {
  return (
    <div className="border-b border-terminal-border bg-terminal-panel sticky top-0 z-20">
      <div className="flex items-center justify-between px-4 py-2">
        <div className="flex items-center gap-3">
          <span className="text-terminal-accent font-bold text-[15px] tracking-widest uppercase">
            MACRO TERMINAL
          </span>
          <span className="text-terminal-border hidden sm:inline">|</span>
          <span className="text-terminal-muted text-[11px] hidden sm:inline">Global Macro Intelligence</span>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-1.5">
            <div className={clsx("w-2 h-2 rounded-full", wsConnected ? "bg-terminal-green animate-pulse" : "bg-terminal-red")} />
            <span className="text-terminal-muted text-[10px]">{wsConnected ? "BINANCE LIVE" : "RECONNECTING"}</span>
          </div>
          <span className="text-terminal-muted text-[11px] hidden md:inline">
            {new Date().toUTCString().replace(" GMT", " UTC").slice(0, -4)}
          </span>
        </div>
      </div>

      {/* Nav tabs */}
      <div className="flex border-t border-terminal-border overflow-x-auto">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => onTab(t.id)}
            className={clsx(
              "px-5 py-2 text-[12px] uppercase tracking-wider border-b-2 transition-colors whitespace-nowrap",
              activeTab === t.id
                ? "border-terminal-accent text-terminal-accent"
                : "border-transparent text-terminal-muted hover:text-terminal-text hover:border-terminal-border",
            )}
          >
            {t.label}
          </button>
        ))}
      </div>
    </div>
  );
}

// ─── Tab views ────────────────────────────────────────────────────────────────

function OverviewTab() {
  return (
    <div className="space-y-4">
      {/* Row: Market grid */}
      <MarketGrid />

      {/* Row: Crypto live */}
      <CryptoLive />

      {/* Row: Yield curve + macro indicators */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-3">
        <YieldCurveChart />
        <MacroLineChart country="USA" indicator="cpi_yoy"        label="US CPI YoY"       color="#ff1744" />
        <MacroLineChart country="USA" indicator="fed_funds_rate"  label="Fed Funds Rate"   color="#ffd600" />
        <MacroLineChart country="USA" indicator="unemployment"    label="Unemployment"     color="#7c4dff" />
      </div>

      {/* Row: Sentiment + calendar preview */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
        <FearGreedGauge />
        <div className="lg:col-span-2">
          <EconomicCalendar />
        </div>
      </div>
    </div>
  );
}

function ChartsTab() {
  return (
    <div className="space-y-4">
      <CandlestickChart />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        <MacroLineChart country="USA" indicator="gdp_growth"    label="US GDP Growth"        color="#00e676" unit="%" />
        <MacroLineChart country="USA" indicator="vix"           label="VIX (Fear Index)"     color="#ff6d00" unit="" />
        <MacroLineChart country="USA" indicator="hy_spread"     label="HY Credit Spread"     color="#e040fb" />
        <MacroLineChart country="USA" indicator="dxy_broad"     label="USD Broad Index"      color="#00d4ff" unit="" />
      </div>
    </div>
  );
}

function MacroTab() {
  return (
    <div className="space-y-4">
      <CountryPanel />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        <MacroLineChart country="USA" indicator="gdp_growth"       label="US GDP Growth"         color="#00e676" />
        <MacroLineChart country="CHN" indicator="gdp_growth"       label="China GDP Growth"      color="#ff1744" />
        <MacroLineChart country="DEU" indicator="gdp_growth"       label="Germany GDP Growth"    color="#ffd600" />
        <MacroLineChart country="JPN" indicator="gdp_growth"       label="Japan GDP Growth"      color="#00d4ff" />
        <MacroLineChart country="USA" indicator="govt_debt_gdp"    label="US Debt/GDP"           color="#e040fb" unit="%" />
        <MacroLineChart country="USA" indicator="current_account_gdp" label="US Current Acct"   color="#ff6d00" />
      </div>
    </div>
  );
}

function SentimentTab() {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
        <FearGreedGauge />
        <div className="lg:col-span-2">
          <NewsFeed />
        </div>
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        <MacroLineChart country="USA" indicator="vix"     label="VIX (Volatility Index)"  color="#ff6d00" unit="" />
        <MacroLineChart country="USA" indicator="hy_spread" label="HY Credit Spread (Risk)" color="#e040fb" />
      </div>
    </div>
  );
}

function CalendarTab() {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
      <div className="lg:col-span-2">
        <EconomicCalendar />
      </div>
      <div className="space-y-3">
        <NewsFeed />
      </div>
    </div>
  );
}

// ─── Dashboard root ───────────────────────────────────────────────────────────
export default function Dashboard() {
  const [activeTab, setActiveTab] = useState<TabId>("overview");
  const { connected } = useWebSocket("prices");

  return (
    <div className="min-h-screen flex flex-col bg-terminal-bg text-terminal-text">
      <Header wsConnected={connected} activeTab={activeTab} onTab={setActiveTab} />
      <TickerBar />

      <main className="flex-1 p-4">
        {activeTab === "overview"  && <OverviewTab />}
        {activeTab === "charts"    && <ChartsTab />}
        {activeTab === "macro"     && <MacroTab />}
        {activeTab === "sentiment" && <SentimentTab />}
        {activeTab === "calendar"  && <CalendarTab />}
      </main>

      <footer className="border-t border-terminal-border px-4 py-1.5 text-terminal-muted text-[10px] flex justify-between flex-wrap gap-1">
        <span>Data: FRED · World Bank · US Treasury · yfinance · Binance WS · CNN Fear&amp;Greed · AAII</span>
        <span>Macro: daily 06:00 UTC · Markets: 15min · Crypto: live · News: 30min</span>
      </footer>
    </div>
  );
}
