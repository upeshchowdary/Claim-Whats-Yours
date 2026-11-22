# Accessibility and Performance

This file separates what is implemented, what is not verified, and what is only a target. It makes no compliance claims.

## Implemented (in code)

- Skip link to main content in AppShell.
- Visible focus ring using `--focus-ring`.
- Form controls with labels (Input, Select).
- Reduced motion: `useReducedMotion` hook and CSS media query (see ANIMATION_SPEC.md).
- Touch targets: 44px minimum is the design rule for controls.
- Status not conveyed by colour alone (StatusBadge, Alert).

## Not verified

- No Lighthouse run.
- No Playwright E2E run; no tests written.
- No axe run (@axe-core/playwright installed, not used).
- No manual keyboard, screen reader or responsive/screenshot QA recorded.
- No frontend lint run recorded.
- No contrast audit recorded. Token contrast was specified but not measured.
- No high-contrast or text-size settings implemented.
- No Hindi locale or translation layer.

## Measured bundle sizes (`npm run build`)

| Chunk | Size | Gzip |
|---|---|---|
| Main | 517.91 kB | 165.60 kB |
| HeroScene3D (lazy) | 940.16 kB | 249.10 kB |
| CSS | 19.10 kB | n/a |

Vite warns that chunks exceed 500 kB. The main chunk is above that threshold.

## Performance rules

- 3D scene is lazy, desktop-only, pauses off-screen, DPR capped at 1.5.
- Static fallback SVG when 3D is not used.

## Targets (not yet measured)

- Targets are goals, not results. Record a measured run before stating any value.
- Main chunk: reduce below 500 kB (target).
- Accessibility: WCAG 2.2 AA is the intended level (target, not claimed).
- Lighthouse scores: to be set after first measured run.
