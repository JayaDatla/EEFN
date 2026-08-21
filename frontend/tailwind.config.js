/** @type {import('tailwindcss').Config} */
// UPGRADE_PLAN.md H.2: colors/type/spacing/radius all reference the CSS custom
// properties defined in src/app/design-tokens.css, so Tailwind utility classes
// (bg-background, text-muted, etc.) stay in sync with the three themes
// (light/dark/red-night) instead of duplicating a second hardcoded palette here.
module.exports = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  darkMode: ["class", '[data-theme="dark"]'],
  theme: {
    extend: {
      colors: {
        background: "var(--color-background)",
        surface: "var(--color-surface)",
        "surface-2": "var(--color-surface-2)",
        border: "var(--color-border)",
        ink: "var(--color-text)",
        muted: "var(--color-text-muted)",
        accent: "var(--color-accent)",
        grade: {
          a: "var(--grade-a)",
          b: "var(--grade-b)",
          c: "var(--grade-c)",
          d: "var(--grade-d)",
          f: "var(--grade-f)",
        },
        severity: {
          critical: "var(--severity-critical)",
          high: "var(--severity-high)",
          medium: "var(--severity-medium)",
          low: "var(--severity-low)",
        },
        status: {
          pass: "var(--status-pass)",
          watch: "var(--status-watch)",
          risk: "var(--status-risk)",
        },
      },
      fontSize: {
        "2xs": "var(--text-2xs)",
        xs: "var(--text-xs)",
        sm: "var(--text-sm)",
        base: "var(--text-base)",
        md: "var(--text-md)",
        lg: "var(--text-lg)",
        xl: "var(--text-xl)",
        "2xl": "var(--text-2xl)",
      },
      spacing: {
        1: "var(--space-1)",
        2: "var(--space-2)",
        3: "var(--space-3)",
        4: "var(--space-4)",
        5: "var(--space-5)",
        6: "var(--space-6)",
        8: "var(--space-8)",
        10: "var(--space-10)",
        12: "var(--space-12)",
        16: "var(--space-16)",
      },
      borderRadius: {
        sm: "var(--radius-sm)",
        DEFAULT: "var(--radius-md)",
        md: "var(--radius-md)",
        lg: "var(--radius-lg)",
        xl: "var(--radius-xl)",
      },
      boxShadow: {
        sm: "var(--shadow-sm)",
        DEFAULT: "var(--shadow-sm)",
        md: "var(--shadow-md)",
        lg: "var(--shadow-lg)",
      },
      fontFamily: {
        mono: ["IBM Plex Mono", "Courier New", "monospace"],
        heading: ["Inter", "sans-serif"],
        sans: ["Inter", "sans-serif"],
      },
    },
  },
  plugins: [],
};
