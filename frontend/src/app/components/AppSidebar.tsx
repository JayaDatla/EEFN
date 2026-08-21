"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity,
  BarChart3,
  Bell,
  Bot,
  GitCompare,
  GitFork,
  Globe2,
  HelpCircle,
  ListChecks,
  Orbit,
  SearchCheck,
  Settings,
  TableProperties,
} from "lucide-react";
import { useTheme, Theme } from "../theme-provider";

const navigation = [
  { href: "/", label: "Triage Queue", icon: Orbit },
  { href: "/fusion", label: "Evidence Explorer", icon: SearchCheck },
  { href: "/compare", label: "Catalog Cross Reference", icon: TableProperties },
  { href: "/graph", label: "Evidence Graph", icon: GitFork },
  { href: "/batch", label: "Batch Workflow", icon: ListChecks },
  { href: "/changes", label: "What Changed", icon: GitCompare },
  // UPGRADE_PLAN.md H.3.10: renamed from "Validation" -- this page shows the deep
  // learning model's demonstration classification pathway, which LIMITATIONS.md
  // §1.7 discloses is trained entirely on synthetic light curves, not a validated
  // classifier. The old label implied more than the page actually delivers.
  { href: "/ai-analysis", label: "DL Model Demo", icon: Activity },
  { href: "/admin", label: "Pipeline Admin", icon: Bell },
  { href: "/predictions", label: "ML Predictions", icon: Bot },
  { href: "/about", label: "What This Tool Does", icon: HelpCircle },
];

// UPGRADE_PLAN.md H.3.10: demo/showcase content for conference/outreach use --
// kept (not deleted), but demoted out of primary navigation and unmistakably
// badged so it can never be confused with the live triage tool.
const galleryNavigation = [
  { href: "/showcase", label: "Research Analytics", icon: BarChart3 },
  { href: "/demo", label: "API Explorer", icon: Globe2 },
];

const THEME_OPTIONS: { value: Theme; label: string }[] = [
  { value: "light", label: "Light" },
  { value: "dark", label: "Dark" },
  { value: "red-night", label: "Night" },
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
        <img src="/logo.png" alt="EEFN Logo" className="h-8 md:h-10 w-auto object-contain rounded-md" />
      </Link>

      <div className="mission-tag">
        <span className="status-dot" /> NETWORK NOMINAL
      </div>

      <ThemeToggle />

      <nav aria-label="Primary navigation" className="sidebar-nav">
        <p>OBSERVATORY</p>
        {navigation.map(({ href, label, icon: Icon }) => {
          const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
          return (
            <Link key={href} href={href} className={active ? "active" : ""}>
              <Icon size={16} />
              <span>{label}</span>
            </Link>
          );
        })}
        <p className="nav-spacer">GALLERY (DEMO CONTENT)</p>
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
        <p className="nav-spacer">SYSTEM</p>
        <Link href="/admin">
          <Settings size={16} />
          <span>Settings</span>
        </Link>
      </nav>

      <div className="sidebar-foot">
        EEFN / 2.0.0
        <br />
        Scientific operations console
      </div>
    </aside>
  );
}
