import { CheckCircle, Clock, HelpCircle, type LucideIcon } from "lucide-react";

const LABELS: Record<string, string> = {
  verified: "Verified",
  pending: "Pending verification",
  unverified: "Not yet verified",
};

const ICONS: Record<string, LucideIcon> = {
  verified: CheckCircle,
  pending: Clock,
  unverified: HelpCircle,
};

const TONE_CLASSES: Record<string, string> = {
  verified: "bg-success-soft text-success",
  pending: "bg-warning-soft text-warning",
  unverified: "bg-primary-soft text-primary",
};

export interface StatusBadgeProps {
  status: "verified" | "pending" | "unverified" | string;
}

export function StatusBadge({ status }: StatusBadgeProps) {
  const Icon = ICONS[status] ?? HelpCircle;
  const label = LABELS[status] ?? status;
  const tone = TONE_CLASSES[status] ?? "bg-primary-soft text-muted";

  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-sm font-medium ${tone}`}>
      <Icon aria-hidden="true" className="size-4" />
      <span>{label}</span>
    </span>
  );
}
