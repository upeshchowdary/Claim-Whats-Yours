import { Suspense, lazy, useEffect, useRef, useState } from "react";
import type { JSX } from "react";
import { useReducedMotion } from "../motion/useReducedMotion";
import { HeroFallback } from "./HeroFallback";

const HeroScene3D = lazy(() => import("./HeroScene3D"));

const DESKTOP_MIN_WIDTH = 768;

function hasWebGL(): boolean {
  try {
    const canvas = document.createElement("canvas");
    return Boolean(canvas.getContext("webgl2") || canvas.getContext("webgl"));
  } catch {
    return false;
  }
}

export function HeroVisual(): JSX.Element {
  const wrapperRef = useRef<HTMLDivElement>(null);
  const reduced = useReducedMotion();
  const [inView, setInView] = useState(false);
  const [webgl] = useState<boolean>(() => hasWebGL());
  const [wideEnough] = useState<boolean>(
    () => typeof window !== "undefined" && window.innerWidth >= DESKTOP_MIN_WIDTH,
  );

  useEffect(() => {
    const element = wrapperRef.current;
    if (!element || typeof IntersectionObserver === "undefined") {
      return;
    }
    const observer = new IntersectionObserver(
      (entries) => {
        setInView(entries.some((entry) => entry.isIntersecting));
      },
      { threshold: 0.1 },
    );
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  const canUse3D = !reduced && inView && wideEnough && webgl;

  return (
    <div
      ref={wrapperRef}
      className="relative aspect-square w-full max-w-[560px]"
      aria-hidden="true"
    >
      {canUse3D ? (
        <Suspense fallback={<HeroFallback />}>
          <HeroScene3D />
        </Suspense>
      ) : (
        <HeroFallback />
      )}
    </div>
  );
}
