import { CheckCircle2, AlertTriangle, Circle } from "lucide-react";
import { ReactNode } from "react";

export function SectionHeading({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="section-heading">
      <div>
        <p className="eyebrow">{eyebrow || "EEFN OPERATIONS"}</p>
        <h1>{title}</h1>
        {description && <p className="section-description">{description}</p>}
      </div>
      {action && <div className="section-action">{action}</div>}
    </div>
  );
}

export function ScientificMetricCard({
  label,
  value,
  detail,
  tone = "blue",
}: {
  label: string;
  value: string | number;
  detail: string;
  tone?: "blue" | "cyan" | "purple" | "gold";
}) {
  return (
    <article className={`scientific-metric tone-${tone}`}>
      <p>{label}</p>
      <strong>{value}</strong>
      <span>{detail}</span>
    </article>
  );
}

export function ConfidenceBadge({ score, label }: { score: number; label?: string }) {
  const tone = score >= 0.8 ? "good" : score >= 0.5 ? "watch" : "risk";
  return <span className={`confidence-badge ${tone}`}>{label || `${Math.round(score * 100)}% confidence`}</span>;
}

export function StatusIndicator({ status }: { status: "pass" | "watch" | "risk" }) {
  const Icon = status === "pass" ? CheckCircle2 : status === "watch" ? AlertTriangle : Circle;
  return (
    <span className={`status-indicator ${status}`}>
      <Icon size={14} /> {status === "pass" ? "Verified" : status === "watch" ? "Review" : "Flagged"}
    </span>
  );
}
