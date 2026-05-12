import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./lib/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // GLCR Brand palette
        glcr: {
          gold: "#C9A84C",
          "gold-light": "#E5C97A",
          "gold-muted": "#A07830",
          navy: "#1A2340",
          "navy-deep": "#0F1628",
          slate: "#2C3654",
          "slate-mid": "#3D4D6E",
        },
        // Semantic surface tokens
        surface: {
          base: "#F5F5F7",
          card: "#FFFFFF",
          elevated: "#FAFAFA",
          overlay: "rgba(0,0,0,0.48)",
        },
        // Zone group accent colors
        zone: {
          blue: "#3B82F6",
          teal: "#14B8A6",
          amber: "#F59E0B",
          rose: "#F43F5E",
          purple: "#8B5CF6",
          emerald: "#10B981",
          orange: "#F97316",
          indigo: "#6366F1",
          sky: "#0EA5E9",
          lime: "#84CC16",
          pink: "#EC4899",
          slate: "#64748B",
        },
      },
      fontFamily: {
        sans: [
          "-apple-system",
          "BlinkMacSystemFont",
          '"SF Pro Display"',
          '"SF Pro Text"',
          "Helvetica Neue",
          "Arial",
          "sans-serif",
        ],
        mono: [
          '"SF Mono"',
          "ui-monospace",
          "SFMono-Regular",
          "Menlo",
          "monospace",
        ],
      },
      borderRadius: {
        xl: "16px",
        "2xl": "20px",
        "3xl": "24px",
        "4xl": "32px",
      },
      boxShadow: {
        card: "0 2px 8px rgba(0,0,0,0.06), 0 0 0 1px rgba(0,0,0,0.04)",
        "card-hover": "0 8px 24px rgba(0,0,0,0.10), 0 0 0 1px rgba(0,0,0,0.05)",
        "card-press": "0 1px 3px rgba(0,0,0,0.06), 0 0 0 1px rgba(0,0,0,0.04)",
        "context-menu": "0 8px 32px rgba(0,0,0,0.18), 0 0 0 1px rgba(0,0,0,0.08)",
        pill: "0 1px 3px rgba(0,0,0,0.08)",
      },
      animation: {
        "fade-up": "fadeUp 0.24s cubic-bezier(0.16, 1, 0.3, 1) forwards",
        "scale-in": "scaleIn 0.18s cubic-bezier(0.16, 1, 0.3, 1) forwards",
        "slide-in-right": "slideInRight 0.28s cubic-bezier(0.16, 1, 0.3, 1) forwards",
        shimmer: "shimmer 1.4s infinite",
        "spin-slow": "spin 3s linear infinite",
      },
      keyframes: {
        fadeUp: {
          from: { opacity: "0", transform: "translateY(8px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        scaleIn: {
          from: { opacity: "0", transform: "scale(0.94)" },
          to: { opacity: "1", transform: "scale(1)" },
        },
        slideInRight: {
          from: { opacity: "0", transform: "translateX(16px)" },
          to: { opacity: "1", transform: "translateX(0)" },
        },
        shimmer: {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
      },
      backdropBlur: {
        xs: "4px",
      },
    },
  },
  plugins: [],
};

export default config;
