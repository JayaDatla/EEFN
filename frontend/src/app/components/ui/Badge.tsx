// UPGRADE_PLAN.md H.2 primitive: one Badge implementation for grade/severity/status
// semantics, always paired with text (never color alone, per the H.1 checklist).
import { ReactNode } from "react";

type Tone = "grade-a" | "grade-b" | "grade-c" | "grade-d" | "grade-f" | "severity-critical" | "severity-high" | "severity-medium" | "severity-low" | "status-pass" | "status-watch" | "status-risk" | "neutral";

const TONE_CLASS: Record<Tone, string> = {
  "grade-a": "bg-grade-a/15 text-grade-a border-grade-a/30",
  "grade-b": "bg-grade-b/15 text-grade-b border-grade-b/30",
  "grade-c": "bg-grade-c/15 text-grade-c border-grade-c/30",
  "grade-d": "bg-grade-d/15 text-grade-d border-grade-d/30",
  "grade-f": "bg-grade-f/15 text-grade-f border-grade-f/30",
  "severity-critical": "bg-severity-critical/15 text-severity-critical border-severity-critical/30",
  "severity-high": "bg-severity-high/15 text-severity-high border-severity-high/30",
  "severity-medium": "bg-severity-medium/15 text-severity-medium border-severity-medium/30",
  "severity-low": "bg-severity-low/15 text-severity-low border-severity-low/30",
  "status-pass": "bg-status-pass/15 text-status-pass border-status-pass/30",
  "status-watch": "bg-status-watch/15 text-status-watch border-status-watch/30",
  "status-risk": "bg-status-risk/15 text-status-risk border-status-risk/30",
  neutral: "bg-surface-2 text-muted border-border",
};

export function Badge({ tone = "neutral", children, icon }: { tone?: Tone; children: ReactNode; icon?: ReactNode }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-[4px] border px-2 py-0.5 font-mono text-[10px] font-medium uppercase tracking-[0.08em] ${TONE_CLASS[tone]}`}
    >
      {icon}
      {children}
    </span>
  );
}

export function healthGradeTone(grade: string | null | undefined): Tone {
  const g = (grade || "").toUpperCase();
  if (g === "A") return "grade-a";
  if (g === "B") return "grade-b";
  if (g === "C") return "grade-c";
  if (g === "D") return "grade-d";
  if (g === "F") return "grade-f";
  return "neutral";
}
