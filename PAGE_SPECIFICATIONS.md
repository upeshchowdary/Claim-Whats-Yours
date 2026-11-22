# Page Specifications

Status key: **built** = implemented and rendering; **placeholder** = route exists with stub content; **blocked** = needs backend support that does not exist in code.

Routes are defined in `frontend/src/app/router.tsx`.

## `/` HomePage: built
- Sections: hero, problem, how-it-works, category, trust, final CTA.
- Hero uses HeroVisual: lazy 3D scene with static HeroFallback SVG (see ANIMATION_SPEC.md).
- No scheme data shown; no invented statistics.

## `/overview` OverviewPage: built
- Explains the product's purpose and the route map at a high level.

## `/how-it-works`: placeholder
- Route exists; full content not written.

## `/schemes`: placeholder
- Scheme list. Will use `GET /api/v1/schemes` (paged). Not built.

## `/schemes/:id`: placeholder
- Scheme detail. Will use `GET /api/v1/schemes/{scheme_id}`. Not built.

## `/check-eligibility`: blocked
- Intake form. Needs an eligibility endpoint, which exists only in the contract.
- Form libraries (react-hook-form, zod) are installed but unused here.

## `/results`: blocked
- Eligibility results. Needs the same eligibility endpoint as intake.
- Wording must be "may qualify" style.

## `/checklist/:id`: placeholder
- Document checklist for a scheme. Not built.

## `/application-guide/:id`: placeholder
- Step-by-step application guide. Not built.

## `/help`: placeholder
## `/settings`: placeholder
- Settings. High-contrast and text-size options are not implemented.
## `/saved`: placeholder
- Saved schemes. Not built; no persistence of user profile is planned for eligibility.

## `*` NotFoundPage: built

## Not created
- `/tracker`: no backend support.
- `/admin`: no backend support.

## Shared layout (all pages)
- AppShell: header, skip link to main content, footer disclaimer.
- Loading: Skeleton. Empty: EmptyState. Errors: ErrorState and Alert.
