import type { ReactNode } from "react";
import { useEffect, useRef } from "react";
import { animate } from "motion/react";
import { useReducedMotion } from "./useReducedMotion";

export interface FloatingNodeProps {
  children: ReactNode;
  className?: string;
}

/**
 * Decorative only: gentle vertical drift (max 6px, ~8s cycle).
 * Do not use on text or interactive controls.
 */
export function FloatingNode({ children, className }: FloatingNodeProps) {
  const reduced = useReducedMotion();
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const node = ref.current;
    if (!node || reduced) return;
    const controls = animate(node, { y: [0, -6] }, {
      duration: 8,
      repeat: Infinity,
      repeatType: "mirror",
      ease: "easeInOut",
    });
    return () => controls.stop();
  }, [reduced]);

  return (
    <div ref={ref} className={className} aria-hidden="true">
      {children}
    </div>
  );
}
