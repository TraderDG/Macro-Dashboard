"use client";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, endpoints } from "@/lib/api";
import { CountryProfile } from "@/types";
import { clsx } from "clsx";

const COUNTRIES = [
  { code: "USA", label: "United States" },
  { code: "CHN", label: "China" },
  { code: "DEU", label: "Germany" },
  { code: "JPN", label: "Japan" },
  { code: "GBR", label: "UK" },
  { code: "IND", label: "India" },
  { code: "BRA", label: "Brazil" },
  { code: "KOR", label: "South Korea" },
];

const KEY_INDICATORS = [
  { key: "gdp_growth",     label: "GDP Growth",  unit: "%" },
  { key: "cpi_yoy",        label: "CPI YoY",     unit: "%" },
  { key: "unemployment",   label: "Unemployment",unit: "%" },
  { key: "current_account_gdp", label: "Current Acct",unit: "%" },
  { key: "govt_debt_gdp",  label: "Debt/GDP",    unit: "%" },
  { key: "gdp_per_capita", label: "GDP/Capita",  unit: "USD" },
];

export function CountryPanel() {
  const [selected, setSelected] = useState("USA");

  const { data, isLoading } = useQuery<CountryProfile>({
    queryKey: ["country-profile", selected],
    queryFn: () => api.get(endpoints.countryProfile(selected)).then((r) => r.data),
    staleTime: 30 * 60 * 1000,
  });

  return (
    <div className="panel p-4">
      <div className="flex items-center gap-2 mb-4 flex-wrap">
        <span className="text-terminal-accent text-[12px] uppercase tracking-widest font-semibold mr-2">
          Country Profile
        </span>
        {COUNTRIES.map((c) => (
          <button
            key={c.code}
            onClick={() => setSelected(c.code)}
            className={clsx(
              "px-2 py-0.5 text-[11px] border rounded transition-colors",
              selected === c.code
                ? "border-terminal-accent text-terminal-accent bg-terminal-accent/10"
                : "border-terminal-border text-terminal-muted hover:border-terminal-accent/50"
            )}
          >
            {c.label}
          </button>
        ))}
      </div>

      {isLoading ? (
        <div className="text-terminal-muted text-center py-6">Loading...</div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
          {KEY_INDICATORS.map(({ key, label, unit }) => {
            const entry = data?.[key];
            const val = entry?.value;
            return (
              <div key={key} className="bg-terminal-bg border border-terminal-border rounded p-3">
                <div className="text-terminal-muted text-[10px] uppercase mb-1">{label}</div>
                <div className="text-terminal-text font-semibold text-base">
                  {val != null
                    ? `${unit === "USD" ? "$" : ""}${val.toLocaleString("en-US", { maximumFractionDigits: 1 })}${unit !== "USD" ? unit : ""}`
                    : "—"}
                </div>
                {entry?.as_of && (
                  <div className="text-terminal-muted text-[10px] mt-1">
                    {new Date(entry.as_of).getFullYear()}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
