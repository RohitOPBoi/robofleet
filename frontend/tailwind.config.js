/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        studio: {
          sand: "#E6D8CC",
          "sand-deep": "#CBB19C",
          porcelain: "#FFFBF8",
          "porcelain-soft": "#F7EFE9",
          terracotta: "#D9533B",
          vermilion: "#D34B33",
          coral: "#E87454",
          bronze: "#3A2820",
          "bronze-light": "#52362A",
          espresso: "#191310",
          ink: "#241B16",
          "ink-secondary": "#58473D",
          muted: "#756257",
          sage: "#2E7D5B",
          amber: "#B4691E",
          crimson: "#B93829",
        },
        rf: {
          bg: "#191310",
          panel: "#291F1A",
          subtle: "#382B24",
          border: "#4A3A31",
          accent: "#D9533B",
          danger: "#B93829",
          warning: "#B4691E",
          success: "#2E7D5B",
          text: "#FAF3EE",
          muted: "#A69386",
        },
      },
      fontFamily: {
        sans: ['"Plus Jakarta Sans"', "Inter", "system-ui", "sans-serif"],
        mono: ['"JetBrains Mono"', "monospace"],
      },
      transitionDuration: {
        press: "130ms",
        ui: "210ms",
        enter: "240ms",
      },
      transitionTimingFunction: {
        "studio-out": "cubic-bezier(0.23, 1, 0.32, 1)",
        "studio-in-out": "cubic-bezier(0.77, 0, 0.175, 1)",
        "studio-drawer": "cubic-bezier(0.32, 0.72, 0, 1)",
      },
    },
  },
  plugins: [],
};
