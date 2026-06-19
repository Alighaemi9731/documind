import type { Config } from "tailwindcss";

export default {
  darkMode: "class",
  content: ["./app/**/*.{ts,tsx,mdx}", "./components/**/*.{ts,tsx,mdx}"],
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
      },
      borderRadius: {
        lg: "var(--radius)",
        xl: "calc(var(--radius) + 0.5rem)",
        "2xl": "calc(var(--radius) + 1rem)",
        "3xl": "calc(var(--radius) + 1.5rem)",
      },
    },
  },
  plugins: [],
} satisfies Config;
