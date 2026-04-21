import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        terminal: {
          bg: "#0a0e1a",
          panel: "#0f1629",
          border: "#1e2d4a",
          text: "#c8d6f0",
          muted: "#4a6080",
          accent: "#00d4ff",
          green: "#00e676",
          red: "#ff1744",
          yellow: "#ffd600",
          purple: "#7c4dff",
        },
      },
      fontFamily: {
        mono: ["JetBrains Mono", "Fira Code", "Consolas", "monospace"],
      },
    },
  },
  plugins: [],
};

export default config;
