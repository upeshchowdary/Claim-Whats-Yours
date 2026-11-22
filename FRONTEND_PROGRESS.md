# Frontend Progress

Last recorded state. Update when a change is verified.

## Done

- Vite + React 19 + TypeScript scaffold in `frontend/`.
- Routing (react-router-dom v7) with route table in `src/app/router.tsx`.
- Design tokens in `src/styles/tokens.css`.
- UI components in `src/components/ui`.
- AppShell layout (header, skip link, footer disclaimer).
- HomePage: hero, problem, how-it-works, category, trust, final CTA.
- OverviewPage and NotFoundPage.
- Motion primitives: useReducedMotion, Reveal, MagneticButton, FloatingNode.
- Card-lift hover in `src/styles/effects.css`.
- HeroVisual with lazy 3D scene and static fallback.
- `npm run build` passes.
- `npm test` passes: 2 files, 4 tests.
- Dev server serves `/` and `/overview` with 200.

## Remaining

- Scheme discovery list and detail pages (`/schemes`, `/schemes/:id`).
- Checklist and application guide pages.
- Help, settings, saved, how-it-works content.
- Eligibility intake and results (blocked on backend endpoint).
- Frontend lint run.
- Contrast audit against tokens.
- Lighthouse, Playwright E2E, axe, responsive and screenshot QA.
- High-contrast and text-size settings.
- Hindi locale.
- Form pages using react-hook-form + zod.

## Known issues

- Main chunk 517.91 kB exceeds Vite's 500 kB warning threshold.
- HeroScene3D chunk is 940.16 kB (lazy, but large).
- HeroScene3D fallback colour `#4A2BC2` is hard-coded outside tokens.css.
- Backend contract mismatches (see API_INTEGRATION.md).
- `/tracker` and `/admin` not created (no backend support).

Status of this document: edited, not test-verified (no shell).
