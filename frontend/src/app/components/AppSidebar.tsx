"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity,
  BarChart3,
  Bell,
  Bot,
  Database,
  GitCompare,
  GitFork,
  HelpCircle,
  ListChecks,
  Orbit,
  SearchCheck,
  TableProperties,
} from "lucide-react";
import { useTheme, Theme } from "../theme-provider";

// DEMO_READINESS_PLAN.md 3.1: 12 flat top-level destinations was more than a reader
// could hold in their head, and buried the two pages that actually carry the project
// (the triage queue and the catalog-disagreement evidence). Grouped into labelled
// sections by the question each page answers, primary work first.
const navigationGroups = [
  {
    title: "Triage",
    items: [
      { href: "/", label: "Triage Queue", icon: Orbit },
    ],
  },
  {
    title: "Evidence",
    items: [
      { href: "/fusion", label: "Evidence Explorer", icon: SearchCheck },
      { href: "/compare", label: "Catalog Cross Reference", icon: TableProperties },
      { href: "/graph", label: "Evidence Graph", icon: GitFork },
    ],
  },
  {
    title: "Models",
    items: [
      { href: "/predictions", label: "ML Predictions", icon: Bot },
      // UPGRADE_PLAN.md H.3.10: renamed from "Validation" -- this page shows the deep
      // learning model's classification pathway. The old label implied more validation
      // than the page actually delivers.
      { href: "/ai-analysis", label: "Light-Curve Vetting", icon: Activity },
    ],
  },
  {
    title: "Operations",
    items: [
      { href: "/batch", label: "Batch Workflow", icon: ListChecks },
      { href: "/changes", label: "What Changed", icon: GitCompare },
      { href: "/admin", label: "Pipeline Admin", icon: Bell },
    ],
  },
];

// De-emphasised: reference/context rather than a working destination.
const secondaryNavigation = [
  { href: "/data-pipeline", label: "Catalogs & Data Flow", icon: Database },
  { href: "/about", label: "What This Tool Does", icon: HelpCircle },
];

// UPGRADE_PLAN.md H.3.10: demo/showcase content for conference/outreach use --
// kept (not deleted), but demoted out of primary navigation and unmistakably
// badged so it can never be confused with the live triage tool.
// DEMO_READINESS_PLAN.md 3.3: /demo re-exports /showcase (identical content), and
// neither matched its former label ("API Explorer" / "Research Analytics"). Collapsed
// to the single honest entry rather than showing the same deck under two invented names.
const galleryNavigation = [
  { href: "/showcase", label: "Project Overview", icon: BarChart3 },
];

const THEME_OPTIONS: { value: Theme; label: string }[] = [
  { value: "light", label: "Light" },
  { value: "dark", label: "Dark" },
];

function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  return (
    <div className="theme-toggle" role="group" aria-label="Theme">
      {THEME_OPTIONS.map((opt) => (
        <button
          key={opt.value}
          type="button"
          aria-pressed={theme === opt.value}
          onClick={() => setTheme(opt.value)}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}

export default function AppSidebar() {
  const pathname = usePathname();

  return (
    <aside className="app-sidebar">
      <Link href="/" className="brand" aria-label="EEFN mission overview">
        <svg className="brand-mark" viewBox="0 0 40 40" fill="none" aria-hidden="true">
          <circle cx="20" cy="20" r="17.5" stroke="currentColor" strokeWidth="1" opacity="0.45" />
          <ellipse cx="20" cy="20" rx="17.5" ry="6.5" transform="rotate(-28 20 20)" stroke="currentColor" strokeWidth="1" opacity="0.9" />
          <circle cx="20" cy="20" r="3.4" fill="currentColor" />
          <circle cx="33.2" cy="12.4" r="1.9" fill="currentColor" />
        </svg>
        <span className="brand-text">
          <strong>EEFN</strong>
          <small>Evidence Fusion Network</small>
        </span>
      </Link>

      <div className="mission-tag">
        <span className="status-dot" /> NETWORK NOMINAL
      </div>

      <ThemeToggle />

      <nav aria-label="Primary navigation" className="sidebar-nav">
        {navigationGroups.map((group, groupIdx) => (
          <React.Fragment key={group.title}>
            <p className={groupIdx === 0 ? undefined : "nav-spacer"}>{group.title.toUpperCase()}</p>
            {group.items.map(({ href, label, icon: Icon }) => {
              const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
              return (
                <Link key={href} href={href} className={active ? "active" : ""}>
                  <Icon size={16} />
                  <span>{label}</span>
                </Link>
              );
            })}
          </React.Fragment>
        ))}

        <p className="nav-spacer">REFERENCE</p>
        {secondaryNavigation.map(({ href, label, icon: Icon }) => {
          const active = pathname.startsWith(href);
          return (
            <Link key={href} href={href} className={active ? "active" : ""}>
              <Icon size={16} />
              <span>{label}</span>
            </Link>
          );
        })}
        {galleryNavigation.map(({ href, label, icon: Icon }) => {
          const active = pathname.startsWith(href);
          return (
            <Link key={href} href={href} className={active ? "active" : ""}>
              <Icon size={16} />
              <span>{label}</span>
              <span className="nav-demo-badge">DEMO</span>
            </Link>
          );
        })}
        {/* Removed: a "SYSTEM > Settings" entry that pointed at /admin -- a mislabelled
            duplicate of "Pipeline Admin" leading to the same page. There is no settings
            screen in this application. */}
      </nav>

      <div className="sidebar-foot">
        EEFN / 2.0.0
        <br />
        Scientific operations console
      </div>
    </aside>
  );
}
