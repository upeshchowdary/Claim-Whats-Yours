import type { ReactNode } from "react";
import { AlertTriangle, CheckCircle, Info, XCircle } from "lucide-react";

export type AlertTone = "info" | "success" | "warning" | "danger";

const TONES: Record<AlertTone, { classes: string; label: string; Icon: typeof Info }> = {
  info: { classes: "border-primary bg-primary-soft text-foreground", label: "Note:", Icon: Info },
  success: { classes: "border-success bg-success-soft text-foreground", label: "Success:", Icon: CheckCircle },
  warning: { classes: "border-warning bg-warning-soft text-foreground", label: "Warning:", Icon: AlertTriangle },
  danger: { classes: "border-danger bg-danger-soft text-foreground", label: "Error:", Icon: XCircle },
};

export interface AlertProps {
  tone?: AlertTone;
  children: ReactNode;
}

export function Alert({ tone = "info", children }: AlertProps) {
  const { classes, label, Icon } = TONES[tone];
  const isLive = tone === "info" || tone === "success";

  return (
    <div
      role={isLive ? "status" : "alert"}
      className={`flex items-start gap-3 rounded-[12px] border p-4 ${classes}`}
    >
      <Icon aria-hidden="true" className="mt-0.5 size-5 shrink-0" />
      <p>
        <span className="font-semibold">{label}</span> {children}
      </p>
    </div>
  );
}
