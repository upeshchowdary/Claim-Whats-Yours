import type { MouseEvent, ReactNode } from "react";
import { Link } from "react-router-dom";
import { motion, useMotionValue, useSpring } from "motion/react";
import { useCanHover, useReducedMotion } from "./useReducedMotion";

export interface MagneticButtonProps {
  children: ReactNode;
  className?: string;
  href?: string;
  onClick?: () => void;
  type?: "button" | "submit" | "reset";
}

const MAX_OFFSET = 6;
const INNER_CLASS = "inline-block";

export function MagneticButton({ children, className, href, onClick, type = "button" }: MagneticButtonProps) {
  const canHover = useCanHover();
  const reduced = useReducedMotion();
  const magnetic = canHover && !reduced;

  const rawX = useMotionValue(0);
  const rawY = useMotionValue(0);
  const x = useSpring(rawX, { stiffness: 300, damping: 20 });
  const y = useSpring(rawY, { stiffness: 300, damping: 20 });

  const handleMove = (event: MouseEvent<HTMLElement>) => {
    if (!magnetic) return;
    const rect = event.currentTarget.getBoundingClientRect();
    const dx = event.clientX - (rect.left + rect.width / 2);
    const dy = event.clientY - (rect.top + rect.height / 2);
    const clamp = (v: number) => Math.max(-MAX_OFFSET, Math.min(MAX_OFFSET, v * 0.2));
    rawX.set(clamp(dx));
    rawY.set(clamp(dy));
  };

  const handleLeave = () => {
    rawX.set(0);
    rawY.set(0);
  };

  const inner = <motion.span className={INNER_CLASS} style={magnetic ? { x, y } : undefined}>{children}</motion.span>;

  if (href && href.startsWith("/")) {
    return (
      <Link to={href} className={className} onClick={onClick} onMouseMove={handleMove} onMouseLeave={handleLeave}>
        {inner}
      </Link>
    );
  }

  if (href) {
    return (
      <a href={href} className={className} onClick={onClick} onMouseMove={handleMove} onMouseLeave={handleLeave}>
        {inner}
      </a>
    );
  }

  return (
    <button type={type} className={className} onClick={onClick} onMouseMove={handleMove} onMouseLeave={handleLeave}>
      {inner}
    </button>
  );
}
