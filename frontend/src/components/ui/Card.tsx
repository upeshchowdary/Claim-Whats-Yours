import type { HTMLAttributes } from "react";

export function Card({ className = "", ...rest }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={`rounded-[16px] border border-border bg-surface p-6 text-foreground ${className}`.trim()}
      {...rest}
    />
  );
}
