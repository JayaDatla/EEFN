"""
UPGRADE_PLAN.md H.4: real WCAG contrast-ratio audit of the design-token palette,
computed directly from the actual hex values in design-tokens.css (not eyeballed).
Run: python scripts/contrast_audit.py
"""


def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def relative_luminance(rgb):
    def chan(c):
        c = c / 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (chan(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(hex1, hex2):
    l1 = relative_luminance(hex_to_rgb(hex1))
    l2 = relative_luminance(hex_to_rgb(hex2))
    lighter, darker = max(l1, l2), min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


THEMES = {
    "light": {
        "background": "#f8fafc", "surface": "#ffffff", "surface-2": "#eef2f7",
        "text": "#151a21", "text-muted": "#4f5c6b", "accent": "#4f46e5", "accent-text": "#ffffff",
        "grade-a": "#1d4ed8", "grade-b": "#2f8fd1", "grade-c": "#7a8f4a", "grade-d": "#bd8128", "grade-f": "#b5482f",
        "severity-critical": "#b5482f", "severity-high": "#bd8128", "severity-medium": "#8a7a2b",
        "status-pass": "#1f7a5c", "status-watch": "#b8842a", "status-risk": "#b5482f",
    },
    "dark": {
        "background": "#0b0e13", "surface": "#151a21", "surface-2": "#232a34",
        "text": "#f8fafc", "text-muted": "#9aa7ba", "accent": "#818cf8", "accent-text": "#1e1b3a",
        "grade-a": "#5b9dff", "grade-b": "#6fc0e0", "grade-c": "#a8c07a", "grade-d": "#e8b563", "grade-f": "#e2795c",
        "severity-critical": "#e2795c", "severity-high": "#e8b563", "severity-medium": "#c9b463",
        "status-pass": "#5fd9ab", "status-watch": "#e8c777", "status-risk": "#f39aa8",
    },
    "red-night": {
        "background": "#0a0000", "surface": "#150202", "surface-2": "#200404",
        "text": "#ff3b30", "text-muted": "#e7352d", "accent": "#ff5c4d", "accent-text": "#0a0000",
        "grade-a": "#ff5c4d", "grade-b": "#ff5c4d", "grade-c": "#d94436", "grade-d": "#b5342a", "grade-f": "#ff3b30",
        "severity-critical": "#ff3b30", "severity-high": "#d94436", "severity-medium": "#bd2c25",
        "status-pass": "#d94436", "status-watch": "#b5342a", "status-risk": "#ff3b30",
    },
}

# (foreground, background, min_ratio, label)
PAIRS = [
    ("text", "background", 4.5, "primary text on page background"),
    ("text", "surface", 4.5, "primary text on card surface"),
    ("text-muted", "background", 4.5, "muted text on page background"),
    ("text-muted", "surface", 4.5, "muted text on card surface"),
    ("accent", "background", 4.5, "accent text/links on page background"),
    ("accent", "surface", 4.5, "accent text/links on card surface"),
    ("accent-text", "accent", 4.5, "text on solid accent buttons"),
    ("grade-a", "surface", 3.0, "grade A badge text (large/UI text threshold)"),
    ("grade-b", "surface", 3.0, "grade B badge text"),
    ("grade-c", "surface", 3.0, "grade C badge text"),
    ("grade-d", "surface", 3.0, "grade D badge text"),
    ("grade-f", "surface", 3.0, "grade F badge text"),
    ("severity-critical", "surface", 3.0, "critical severity text"),
    ("severity-high", "surface", 3.0, "high severity text"),
    ("severity-medium", "surface", 3.0, "medium severity text"),
    ("status-pass", "surface", 3.0, "pass status text"),
    ("status-watch", "surface", 3.0, "watch status text"),
    ("status-risk", "surface", 3.0, "risk status text"),
]

if __name__ == "__main__":
    failures = []
    for theme_name, tokens in THEMES.items():
        print(f"\n=== {theme_name} ===")
        for fg, bg, minimum, label in PAIRS:
            ratio = contrast_ratio(tokens[fg], tokens[bg])
            status = "PASS" if ratio >= minimum else "FAIL"
            print(f"  [{status}] {label}: {fg} on {bg} = {ratio:.2f}:1 (need >= {minimum})")
            if ratio < minimum:
                failures.append((theme_name, label, fg, bg, ratio, minimum))

    print("\n" + "=" * 60)
    if failures:
        print(f"{len(failures)} FAILING pair(s):")
        for theme_name, label, fg, bg, ratio, minimum in failures:
            print(f"  {theme_name}: {label} ({fg} on {bg}) = {ratio:.2f}:1, needs {minimum}:1")
    else:
        print("All pairs pass their WCAG threshold.")
