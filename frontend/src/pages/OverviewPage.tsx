import { Link } from "react-router-dom";
import { Card } from "../components/ui/Card";
import { buttonClasses } from "../components/ui/Button";

interface OverviewCard {
  title: string;
  description: string;
  to: string;
  linkText: string;
}

const WHAT_YOU_CAN_DO: OverviewCard[] = [
  {
    title: "Explore schemes",
    description: "Browse by state, category and keyword.",
    to: "/schemes",
    linkText: "Explore schemes",
  },
  {
    title: "Check eligibility",
    description: "Answer a short guided set of questions. You choose what to share.",
    to: "/check-eligibility",
    linkText: "Check eligibility",
  },
  {
    title: "Prepare documents",
    description: "A checklist for each scheme, marked by you.",
    to: "/schemes",
    linkText: "Prepare documents",
  },
  {
    title: "Follow application steps",
    description: "Plain-language steps with official links.",
    to: "/schemes",
    linkText: "Follow application steps",
  },
];

const HOW_IT_WORKS_STEPS = [
  "Tell us about your situation.",
  "Discover schemes that may match.",
  "Understand documents and application steps.",
];

const IMPORTANT_NOTES = [
  "Eligibility is an indication, not a government decision.",
  "Scheme information may change. Verify current requirements with the official department or portal.",
  "No Aadhaar, PAN, bank details or passwords are needed to explore.",
  "This is an independent platform, not a government website.",
];

export default function OverviewPage() {
  return (
    <div className="flex flex-col gap-12">
      <section className="flex flex-col gap-4">
        <h1 className="text-3xl font-bold text-foreground">Overview of Claim What's Yours</h1>
        <p className="max-w-prose text-lg text-muted">
          Claim What's Yours is an independent discovery platform. It helps you find government schemes that may match
          your situation, understand the documents you might need, and see the official steps to apply.
        </p>
      </section>

      <section aria-labelledby="overview-what-you-can-do" className="flex flex-col gap-6">
        <h2 id="overview-what-you-can-do" className="text-2xl font-semibold text-foreground">
          What you can do
        </h2>
        <ul className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
          {WHAT_YOU_CAN_DO.map((card) => (
            <li key={card.title} className="flex">
              <Card className="flex w-full flex-col gap-3">
                <h3 className="text-lg font-semibold text-foreground">{card.title}</h3>
                <p className="text-muted">{card.description}</p>
                <Link to={card.to} className="mt-auto font-semibold text-primary hover:text-primary-dark">
                  {card.linkText}
                </Link>
              </Card>
            </li>
          ))}
        </ul>
      </section>

      <section aria-labelledby="overview-how-it-works" className="flex flex-col gap-6">
        <h2 id="overview-how-it-works" className="text-2xl font-semibold text-foreground">
          How it works
        </h2>
        <ol className="flex flex-col gap-4">
          {HOW_IT_WORKS_STEPS.map((step, index) => (
            <li key={step} className="flex items-start gap-4 rounded-[16px] border border-border bg-surface p-4">
              <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-primary-soft font-semibold text-primary">
                {index + 1}
              </span>
              <span className="text-foreground">{step}</span>
            </li>
          ))}
        </ol>
      </section>

      <section aria-labelledby="overview-important" className="flex flex-col gap-6">
        <h2 id="overview-important" className="text-2xl font-semibold text-foreground">
          Important to know
        </h2>
        <ul className="flex list-disc flex-col gap-2 pl-6 text-muted">
          {IMPORTANT_NOTES.map((note) => (
            <li key={note}>{note}</li>
          ))}
        </ul>
      </section>

      <div>
        <Link to="/check-eligibility" className={buttonClasses("primary", "lg")}>
          Start checking
        </Link>
      </div>
    </div>
  );
}
