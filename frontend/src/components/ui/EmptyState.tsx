import type { ReactNode } from "react";

export interface EmptyStateProps {
  title: string;
  description: string;
  action?: ReactNode;
}

export function EmptyState({ title, description, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-start gap-3 rounded-[16px] border border-border bg-surface p-6">
      <h2 className="text-xl font-semibold text-foreground">{title}</h2>
      <p className="text-muted">{description}</p>
      {action ? <div>{action}</div> : null}
    </div>
  );
}
