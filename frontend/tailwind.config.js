/** @type {import('tailwindcss').Config} */
// UPGRADE_PLAN.md H.2: colors/type/spacing/radius all reference the CSS custom
// properties defined in src/app/design-tokens.css, so Tailwind utility classes
// (bg-background, text-muted, etc.) stay in sync with the three themes
// (light/dark/red-night) instead of duplicating a second hardcoded palette here.

// Tailwind can't apply opacity modifiers (bg-accent/10, border-status-pass/30, ...) to a
// color that is a bare CSS variable, so those classes were silently never generated.
// Resolving the modifier with color-mix keeps every theme token usable with /NN.
const tok = (name) => ({ opacityValue }) => {
  if (opacityValue === undefined) return `var(${name})`;
  const n = parseFloat(opacityValue);
  if (!Number.isNaN(n) && /^[0-9.]+$/.test(String(opacityValue))) {
    return n >= 1 ? `var(${name})` : `color-mix(in srgb, var(${name}) ${Math.round(n * 1000) / 10}%, transparent)`;
  }
  // Tailwind passes e.g. "var(--tw-border-opacity)" for plain border-*/text-*/bg-* utilities.
  return `color-mix(in srgb, var(${name}) calc(${opacityValue} * 100%), transparent)`;
};

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
        background: tok("--color-background"),
        surface: tok("--color-surface"),
        "surface-2": tok("--color-surface-2"),
        border: tok("--color-border"),
        hairline: tok("--color-hairline"),
        ink: tok("--color-text"),
        muted: tok("--color-text-muted"),
        accent: tok("--color-accent"),
        grade: {
          a: tok("--grade-a"),
          b: tok("--grade-b"),
          c: tok("--grade-c"),
          d: tok("--grade-d"),
          f: tok("--grade-f"),
        },
        severity: {
          critical: tok("--severity-critical"),
          high: tok("--severity-high"),
          medium: tok("--severity-medium"),
          low: tok("--severity-low"),
        },
        status: {
          pass: tok("--status-pass"),
          watch: tok("--status-watch"),
          risk: tok("--status-risk"),
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
      borderColor: { DEFAULT: "var(--color-hairline)" },
      divideColor: { DEFAULT: "var(--color-hairline)" },
      ringColor: { DEFAULT: "var(--color-accent)" },
      fontFamily: {
        mono: ["var(--font-data)"],
        heading: ["var(--font-body)"],
        sans: ["var(--font-body)"],
        // Design pass 2026-08-21: a real display face for page headlines, available
        // as a utility class for the hand-rolled headings that don't go through the
        // shared SectionHeading component (see globals.css .section-heading h1).
        display: ["var(--font-display)"],
      },
    },
  },
  plugins: [],
};
