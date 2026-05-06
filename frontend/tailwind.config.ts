import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        canvas: "rgb(var(--color-canvas) / <alpha-value>)",
        ink: "rgb(var(--color-ink) / <alpha-value>)",
        muted: "rgb(var(--color-muted) / <alpha-value>)",
        accent: "rgb(var(--color-accent) / <alpha-value>)",
        "accent-soft": "rgb(var(--color-accent-soft) / <alpha-value>)",
        slateLine: "rgb(var(--color-slate-line) / <alpha-value>)",
        warning: "rgb(var(--color-warning) / <alpha-value>)",
        danger: "rgb(var(--color-danger) / <alpha-value>)",
        success: "rgb(var(--color-success) / <alpha-value>)"
      },
      fontFamily: {
        display: ["Fraunces", "serif"],
        sans: ["Manrope", "sans-serif"]
      },
      boxShadow: {
        premium: "var(--shadow-premium)",
        float: "var(--shadow-float)",
        soft: "var(--shadow-soft)",
        lift: "var(--shadow-lift)"
      },
      backgroundImage: {
        halo: "var(--background-halo)"
      }
    }
  },
  plugins: []
};

export default config;
