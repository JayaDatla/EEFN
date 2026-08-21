// UPGRADE_PLAN.md H.2 primitive: one Callout/Alert implementation, used for every
// explicit error/unavailable/warning state (A.14, H.4) instead of ad hoc styled divs.
import { ReactNode } from "react";
import { AlertTriangle, Info, AlertOctagon, CheckCircle2 } from "lucide-react";

type Tone = "info" | "warning" | "critical" | "success";

const TONE_CONFIG: Record<Tone, { className: string; Icon: typeof Info }> = {
  info: { className: "border-accent/30 bg-accent/10 text-accent", Icon: Info },
  warning: { className: "border-severity-high/30 bg-severity-high/10 text-severity-high", Icon: AlertTriangle },
  critical: { className: "border-severity-critical/30 bg-severity-critical/10 text-severity-critical", Icon: AlertOctagon },
  success: { className: "border-status-pass/30 bg-status-pass/10 text-status-pass", Icon: CheckCircle2 },
};

export function Callout({ tone = "info", title, children }: { tone?: Tone; title?: string; children: ReactNode }) {
  const { className, Icon } = TONE_CONFIG[tone];
  return (
    <div className={`flex items-start gap-3 rounded-lg border px-4 py-3 text-xs ${className}`} role={tone === "critical" || tone === "warning" ? "alert" : "status"}>
      <Icon size={16} className="mt-0.5 shrink-0" />
      <div>
        {title && <p className="mb-0.5 font-semibold">{title}</p>}
        <div className="text-ink/90">{children}</div>
      </div>
    </div>
  );
}
