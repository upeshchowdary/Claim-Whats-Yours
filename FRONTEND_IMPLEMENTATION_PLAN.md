# Frontend Implementation Plan

Scope: the citizen-facing web client for Claim What's Yours. Backend rules live in `docs/backend/`; this file covers the `frontend/` app only.

## Architecture decision

- Vite + React 19 + TypeScript, chosen over Next.js.
- Reason: no frontend existed, and the app is a client-side app with no SSR requirement.

## Stack

| Concern | Choice |
|---|---|
| Build | Vite, `npm run build` (`tsc -b && vite build`) |
| UI | React 19, TypeScript |
| Routing | react-router-dom v7, `createBrowserRouter` in `src/app/router.tsx` |
| Data | @tanstack/react-query |
| Styling | Tailwind v4 via `@tailwindcss/vite`; semantic tokens in `src/styles/tokens.css` |
| Forms | react-hook-form + zod installed; no form pages yet |
| Motion | motion (v14) |
| 3D | three, @react-three/fiber, @react-three/drei (hero only) |
| Tests | vitest + jsdom + @testing-library/react |
| E2E / a11y | Playwright and @axe-core/playwright installed; no E2E tests written |

Not installed or not used: GSAP, Lenis, next-intl/i18next (no translation layer yet), shadcn/ui/Radix.

## Component layout

- `src/components/ui`: Button, Card, Input, Select, Alert, StatusBadge, Skeleton, EmptyState, ErrorState.
- `src/components/layout`: AppShell (header, skip link, footer disclaimer).
- `src/components/motion`: useReducedMotion, Reveal, MagneticButton, FloatingNode.
- `src/components/hero`: HeroVisual, lazy HeroScene3D, static HeroFallback SVG.
- `src/pages`: one file per route; placeholders where noted in PAGE_SPECIFICATIONS.md.
- `src/lib/api`: client and error mapping (see API_INTEGRATION.md).

## Route table

| Path | Component | State |
|---|---|---|
| `/` | HomePage | built |
| `/overview` | OverviewPage | built |
| `/how-it-works` | placeholder | placeholder |
| `/schemes`, `/schemes/:id` | placeholder | placeholder |
| `/check-eligibility`, `/results` | placeholder | blocked by backend |
| `/checklist/:id`, `/application-guide/:id` | placeholder | placeholder |
| `/help`, `/settings`, `/saved` | placeholder | placeholder |
| `*` | NotFoundPage | built |

Not created: `/tracker`, `/admin` (no backend support).

## API plan

- Read-only scheme browsing first, against implemented backend endpoints.
- Eligibility, tracking, categories and admin wait for backend code; contract exists only in `docs/backend/API_CONTRACT.md`.
- Demo fixtures are gated by `VITE_USE_FIXTURES` and labelled as demo data.

## Phases

| Phase | Status |
|---|---|
| 1. Scaffold, tokens, UI primitives, AppShell | done |
| 2. HomePage, OverviewPage, NotFound | done |
| 3. Motion primitives, card-lift, hero visual (3D + fallback) | done |
| 4. Build and unit tests passing | done |
| 5. Scheme discovery and detail pages | not started (placeholder) |
| 6. Intake and results (needs eligibility endpoint) | blocked |
| 7. Checklist, application guide, help, settings, saved | not started |
| 8. Accessibility, performance and responsive QA | not started |
| 9. E2E tests (Playwright + axe) | not started |

Status detail: see FRONTEND_PROGRESS.md.
