# Animation Spec

Motion is decorative. Every effect must work with reduced motion on and must not block content.

## Motion tokens

| Token | Range | Use |
|---|---|---|
| fast | 120-180ms (`--duration-fast` = 150ms) | Hover, press, focus |
| standard | 180-280ms (`--duration-standard` = 220ms) | Panel and state changes |
| reveal | 350-650ms (`--duration-reveal` = 500ms) | Section entrance |
| easing | `[0.2, 0.7, 0.2, 1]` (`--ease-standard`) | All transitions |

## Effects

| Effect | Where | Implementation | Reduced motion | Touch |
|---|---|---|---|---|
| Reveal | Homepage sections | `src/components/motion/Reveal.tsx` (motion) | Renders content immediately, no translate | Same as desktop |
| MagneticButton | Primary CTAs | `src/components/motion/MagneticButton.tsx` | No pointer-follow; plain button | Pointer-follow disabled |
| FloatingNode | Decorative nodes | `src/components/motion/FloatingNode.tsx` | Static | Static |
| Card lift | Cards on hover | `src/styles/effects.css` | Hover shadow only, no translate | Hover not applied |
| Hero 3D | Hero visual | `src/components/hero/HeroScene3D.tsx` | Static HeroFallback SVG | Static HeroFallback SVG |

`useReducedMotion` (`src/components/motion/useReducedMotion.ts`) reads `prefers-reduced-motion`.
`tokens.css` also shortens all CSS animation and transition durations to 0.01ms under that media query.

## 3D rules (hero only)

- Lazy-loaded: the scene chunk is not in the main bundle.
- Desktop only: rendered only at width >= 768px.
- Requires WebGL. Without it, HeroFallback is shown.
- Requires no reduced motion preference.
- Renders only while in view; pauses when scrolled out of view.
- Device pixel ratio capped at 1.5.
- The 3D scene reads `--primary` at runtime; fallback `#4A2BC2`.

## Not used

- GSAP, Lenis (smooth scroll). Not installed.

## Verification status

- Reduced-motion and touch fallbacks are implemented in code.
- No manual or automated check of these fallbacks has been recorded.
