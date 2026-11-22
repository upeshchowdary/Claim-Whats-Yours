import { Link } from "react-router-dom";
import { Card } from "../components/ui/Card";
import { buttonClasses } from "../components/ui/Button";
import { HeroVisual } from "../components/hero/HeroVisual";
import { Reveal } from "../components/motion/Reveal";
import { MagneticButton } from "../components/motion/MagneticButton";
import { FloatingNode } from "../components/motion/FloatingNode";

const HOW_IT_WORKS_STEPS = [
  "Tell us about your situation.",
  "Discover schemes that may match.",
  "Understand documents and application steps.",
];

const CATEGORIES = [
  "Education",
  "Healthcare",
  "Housing",
  "Agriculture",
  "Pension and social security",
  "Employment and livelihood",
  "Women and child welfare",
  "Other public benefits",
];

const TRUST_POINTS = [
  "Scheme information is linked to official sources.",
  "Eligibility is an indication, not a government decision.",
  "Scheme information may change. Verify current requirements with the official department or portal.",
  "Discovery does not require Aadhaar.",
];

const STEP_DELAYS = [0, 0.08, 0.16];

export function HomePage() {
  return (
    <div className="flex flex-col gap-20">
      <section aria-labelledby="home-hero" className="grid items-center gap-12 md:grid-cols-2">
        <div className="flex flex-col gap-6">
          <p className="text-sm font-semibold uppercase tracking-wide text-primary">
            Government benefits, made easier to discover.
          </p>
          <h1 id="home-hero" className="text-4xl font-bold text-foreground md:text-5xl">
            You may be entitled to more than you know.
          </h1>
          <p className="max-w-prose text-lg text-muted">
            Claim What's Yours helps you discover government schemes that may match your circumstances, understand the
            documents you may need, and see the official steps to apply.
          </p>
          <div className="flex flex-wrap items-center gap-4">
            <MagneticButton href="/check-eligibility" className={buttonClasses("primary", "lg")}>
              Discover My Benefits
            </MagneticButton>
            <Link to="/schemes" className="font-semibold text-primary hover:text-primary-dark">
              Explore Schemes
            </Link>
          </div>
          <p className="text-sm text-muted">Free to explore · No Aadhaar required</p>
        </div>

        <div className="flex justify-center md:justify-end">
          <FloatingNode className="w-full">
            <HeroVisual />
          </FloatingNode>
        </div>
      </section>

      <section aria-labelledby="home-problem" className="flex flex-col gap-4">
        <Reveal>
          <h2 id="home-problem" className="text-3xl font-semibold text-foreground">
            The benefits exist. Finding them shouldn't be difficult.
          </h2>
          <p className="mt-4 max-w-prose text-lg text-muted">
            Information is scattered across many portals, and eligibility rules are written in dense legal language.
            Many people who qualify never find out.
          </p>
        </Reveal>
      </section>

      <section aria-labelledby="home-how-it-works" className="flex flex-col gap-6">
        <Reveal>
          <h2 id="home-how-it-works" className="text-3xl font-semibold text-foreground">
            How it works
          </h2>
        </Reveal>
        <ol className="grid grid-cols-1 gap-4 md:grid-cols-3">
          {HOW_IT_WORKS_STEPS.map((step, index) => (
            <li key={step} className="flex">
              <Reveal delay={STEP_DELAYS[index]} className="flex w-full">
                <Card className="card-lift flex w-full flex-col gap-3">
                  <span className="flex size-10 items-center justify-center rounded-full bg-primary-soft font-semibold text-primary">
                    {index + 1}
                  </span>
                  <p className="text-lg font-semibold text-foreground">{step}</p>
                </Card>
              </Reveal>
            </li>
          ))}
        </ol>
      </section>

      <section aria-labelledby="home-categories" className="flex flex-col gap-6">
        <Reveal>
          <h2 id="home-categories" className="text-3xl font-semibold text-foreground">
            Discover by category
          </h2>
        </Reveal>
        <ul className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {CATEGORIES.map((category) => (
            <li key={category} className="flex">
              <Link to="/schemes" className="card-lift flex w-full">
                <Card className="flex w-full flex-col gap-2">
                  <h3 className="text-lg font-semibold text-foreground">{category}</h3>
                  <span className="mt-auto text-sm font-semibold text-primary">Explore schemes</span>
                </Card>
              </Link>
            </li>
          ))}
        </ul>
      </section>

      <section aria-labelledby="home-trust" className="flex flex-col gap-6">
        <Reveal>
          <h2 id="home-trust" className="text-3xl font-semibold text-foreground">
            Trust and transparency
          </h2>
        </Reveal>
        <ul className="flex list-disc flex-col gap-2 pl-6 text-muted">
          {TRUST_POINTS.map((point) => (
            <li key={point}>{point}</li>
          ))}
        </ul>
      </section>

      <section aria-labelledby="home-cta" className="flex flex-col items-start gap-6">
        <Reveal>
          <h2 id="home-cta" className="text-3xl font-semibold text-foreground">
            Start with your situation. Discover your possibilities.
          </h2>
          <div className="mt-6">
            <MagneticButton href="/check-eligibility" className={buttonClasses("primary", "lg")}>
              Check My Eligibility
            </MagneticButton>
          </div>
        </Reveal>
      </section>
    </div>
  );
}

export default HomePage;

