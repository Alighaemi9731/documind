import type { Config } from "tailwindcss";

/**
 * Design tokens are CSS variables (app/globals.css) so light/dark + the runtime
 * branding accent are swappable without a rebuild. Tailwind maps them to its
 * utility scale here. Dark mode uses the `class` strategy (the `.dark` class is
 * set before hydration to avoid a first-paint flash — see ThemeScript).
 */
export default {
  darkMode: "class",
  content: ["./app/**/*.{ts,tsx,mdx}", "./components/**/*.{ts,tsx,mdx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        muted: "hsl(var(--muted))",
        "muted-foreground": "hsl(var(--muted-foreground))",
        accent: "hsl(var(--accent))",
        "accent-foreground": "hsl(var(--accent-foreground))",
        border: "hsl(var(--border))",
        card: "hsl(var(--card))",
        "card-foreground": "hsl(var(--card-foreground))",
        ring: "hsl(var(--ring))",
        success: "hsl(var(--success))",
        warning: "hsl(var(--warning))",
        danger: "hsl(var(--danger))",
        glass: "hsl(var(--glass))",
      },
      fontFamily: {
        sans: [
          "-apple-system",
          "BlinkMacSystemFont",
          '"Segoe UI"',
          "Roboto",
          "Helvetica",
          "Arial",
          '"Vazirmatn"',
          "sans-serif",
          '"Apple Color Emoji"',
          '"Segoe UI Emoji"',
        ],
        mono: [
          "ui-monospace",
          "SFMono-Regular",
          "Menlo",
          "Monaco",
          "Consolas",
          '"Liberation Mono"',
          "monospace",
        ],
      },
      borderRadius: {
        lg: "var(--radius)",
        xl: "calc(var(--radius) + 0.375rem)",
        "2xl": "calc(var(--radius) + 0.75rem)",
        "3xl": "calc(var(--radius) + 1.25rem)",
      },
      boxShadow: {
        sm: "var(--shadow-sm)",
        DEFAULT: "var(--shadow-md)",
        md: "var(--shadow-md)",
        lg: "var(--shadow-lg)",
        xl: "var(--shadow-xl)",
      },
      spacing: {
        "4.5": "1.125rem",
        "18": "4.5rem",
        "112": "28rem",
        "128": "32rem",
      },
      maxWidth: {
        "8xl": "88rem",
      },
      keyframes: {
        "fade-in": {
          from: { opacity: "0", transform: "translateY(2px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        "fade-in": "fade-in 0.18s ease-out both",
      },
    },
  },
  plugins: [],
} satisfies Config;
