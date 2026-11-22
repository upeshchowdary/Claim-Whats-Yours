# Design System

Source of truth: `frontend/src/styles/tokens.css`. Components use semantic token names, not raw hex.

## Colour tokens

| Token | Hex | Use |
|---|---|---|
| `--color-background` / `--background` | #FAFAF8 | Page background |
| `--color-surface` / `--surface` | #FFFFFF | Cards, inputs |
| `--color-foreground` / `--foreground` | #191827 | Body text |
| `--color-muted` / `--muted` | #626174 | Secondary text |
| `--color-primary` / `--primary` | #4A2BC2 | Primary actions, links |
| `--color-primary-dark` | #35208F | Primary hover |
| `--color-primary-soft` | #F0ECFF | Tinted panels |
| `--color-primary-foreground` | #FFFFFF | Text on primary |
| `--color-accent` / `--accent` | #E89C30 | Accent (saffron) |
| `--color-saffron-soft` | #FFF4E2 | Accent panels |
| `--color-success` / `--success` | #247A4B | Success text/icon |
| `--color-success-soft` | #EAF6EF | Success panel |
| `--color-warning` / `--warning` | #946000 | Warning text/icon |
| `--color-warning-soft` | #FFF5DF | Warning panel |
| `--color-danger` / `--danger` | #B42318 | Error text/icon |
| `--color-danger-soft` | #FDECEC | Error panel |
| `--color-border` / `--border` | #E9E7EF | Borders, dividers |
| `--color-dark-surface` | #171522 | Dark surfaces |
| `--color-focus-ring` / `--focus-ring` | #4A2BC2 | Focus outline |

Exception: `HeroScene3D` reads `--primary` at runtime and falls back to `#4A2BC2`. This is the only hex used outside `tokens.css`.

## Typography

- Font: `--font-sans`: Noto Sans, Noto Sans Devanagari, system-ui, then system fallbacks.
- Devanagari support is in the font stack; no Hindi locale is implemented.
- Type scale: not yet tokenised. Sizes are set per component with Tailwind utilities.

## Layout

- Content width: `--container-content` = 1240px.
- Spacing and radius: no spacing or radius tokens are defined in `tokens.css`. Values come from Tailwind utilities in components; no scale has been recorded.

## Shadows

| Token | Value |
|---|---|
| `--shadow-card` | `0 8px 24px rgb(25 24 39 / 0.08)` |
| `--shadow-card-hover` | `0 12px 32px rgb(25 24 39 / 0.12)` |

## Motion tokens

| Token | Value |
|---|---|
| `--ease-standard` | `cubic-bezier(0.2, 0.7, 0.2, 1)` |
| `--duration-fast` | 150ms |
| `--duration-standard` | 220ms |
| `--duration-reveal` | 500ms |

See ANIMATION_SPEC.md for ranges and reduced-motion rules.

## Usage rules

- Use semantic tokens (`--primary`, `--danger`) or their Tailwind `color-*` equivalents. Do not add new hex values in components.
- Status is never colour-only: pair each status colour with text or an icon (StatusBadge, Alert).
- Focus must always be visible using `--focus-ring`.
- No certification badges or government-seal imagery.
- Eligibility wording uses "may qualify" style, never a guaranteed outcome.
