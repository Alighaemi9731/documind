"use client";

/**
 * Lazy Framer Motion bridge (ARCHITECTURE.md §4/§11).
 *
 * Framer Motion is dynamically imported so it is NEVER part of the initial /
 * landing chunk — the marketing page stays static. Components that want animated
 * entrances render {@link MotionDiv}, which:
 *   - server-renders (and first-paints) as a plain <div> with the same className,
 *     so there is no layout shift and no Framer in the critical path;
 *   - upgrades to an animated `motion.div` once the library has loaded client-side
 *     AND the user has not requested reduced motion.
 *
 * This keeps animations "progressive enhancement": correct and instant without
 * JS, tastefully animated with it.
 */

import dynamic from "next/dynamic";
import { type ComponentType, type ReactNode, useEffect, useState } from "react";

import { cn } from "@/lib/cn";

/**
 * Test/SSR escape hatch: when Framer cannot or should not load (jsdom, reduced
 * motion), components render a plain <div>. Setting this to `true` forces the
 * static path so component tests never need to resolve the dynamic chunk.
 */
const DISABLE_MOTION =
  typeof process !== "undefined" && process.env.NEXT_PUBLIC_DISABLE_MOTION === "1";

type Variant = "fade" | "fade-up" | "scale";

const VARIANTS: Record<Variant, { initial: object; animate: object; exit: object }> = {
  fade: {
    initial: { opacity: 0 },
    animate: { opacity: 1 },
    exit: { opacity: 0 },
  },
  "fade-up": {
    initial: { opacity: 0, y: 8 },
    animate: { opacity: 1, y: 0 },
    exit: { opacity: 0, y: 8 },
  },
  scale: {
    initial: { opacity: 0, scale: 0.96 },
    animate: { opacity: 1, scale: 1 },
    exit: { opacity: 0, scale: 0.96 },
  },
};

/** Lazily-loaded `motion.div` (no SSR — the static fallback handles first paint). */
const LazyMotionDiv = dynamic(
  () => import("framer-motion").then((m) => m.motion.div as ComponentType<Record<string, unknown>>),
  { ssr: false },
);

function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    if (typeof window === "undefined" || !window.matchMedia) return;
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReduced(mq.matches);
    const onChange = () => setReduced(mq.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);
  return reduced;
}

export interface MotionDivProps {
  children: ReactNode;
  className?: string;
  variant?: Variant;
  /** Override the transition duration in seconds. */
  duration?: number;
  role?: string;
  "aria-modal"?: boolean;
  "aria-label"?: string;
  "aria-labelledby"?: string;
  "aria-describedby"?: string;
}

export function MotionDiv({
  children,
  className,
  variant = "fade",
  duration = 0.18,
  ...rest
}: MotionDivProps) {
  const reduced = usePrefersReducedMotion();
  const [enabled, setEnabled] = useState(false);

  // Only opt into the animated path after mount + when motion is allowed.
  useEffect(() => {
    if (!reduced && !DISABLE_MOTION) setEnabled(true);
  }, [reduced]);

  if (!enabled) {
    return (
      <div className={cn(className)} {...rest}>
        {children}
      </div>
    );
  }

  const v = VARIANTS[variant];
  return (
    <LazyMotionDiv
      className={className}
      initial={v.initial}
      animate={v.animate}
      exit={v.exit}
      transition={{ duration, ease: [0.22, 1, 0.36, 1] }}
      {...rest}
    >
      {children}
    </LazyMotionDiv>
  );
}
