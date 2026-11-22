import { useState } from "react";
import { Link, Outlet } from "react-router-dom";
import { Menu, X } from "lucide-react";
import { buttonClasses } from "../ui/Button";

const NAV_LINKS = [
  { to: "/overview", label: "Overview" },
  { to: "/how-it-works", label: "How it works" },
  { to: "/schemes", label: "Explore schemes" },
  { to: "/help", label: "Help" },
];

export function AppShell() {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <div className="flex min-h-dvh flex-col bg-background text-foreground">
      <a href="#main" className="skip-link">
        Skip to main content
      </a>

      <header className="border-b border-border bg-surface">
        <div className="mx-auto flex max-w-content items-center justify-between gap-4 px-4 py-3">
          <Link to="/" className="text-lg font-bold text-primary">
            Claim What's Yours
          </Link>

          <nav aria-label="Primary" className="hidden items-center gap-6 md:flex">
            {NAV_LINKS.map((link) => (
              <Link key={link.to} to={link.to} className="text-foreground hover:text-primary">
                {link.label}
              </Link>
            ))}
            <Link to="/check-eligibility" className={buttonClasses("primary")}>
              Find My Benefits
            </Link>
          </nav>

          <button
            type="button"
            className={`${buttonClasses("ghost")} md:hidden`}
            aria-expanded={mobileOpen}
            aria-controls="mobile-nav"
            onClick={() => setMobileOpen((open) => !open)}
          >
            {mobileOpen ? <X aria-hidden="true" className="size-5" /> : <Menu aria-hidden="true" className="size-5" />}
            <span>{mobileOpen ? "Close menu" : "Menu"}</span>
          </button>
        </div>

        <nav
          id="mobile-nav"
          aria-label="Mobile"
          hidden={!mobileOpen}
          className="border-t border-border px-4 py-3 md:hidden"
        >
          <ul className="flex flex-col gap-2">
            {NAV_LINKS.map((link) => (
              <li key={link.to}>
                <Link to={link.to} className="block py-2 text-foreground" onClick={() => setMobileOpen(false)}>
                  {link.label}
                </Link>
              </li>
            ))}
            <li>
              <Link
                to="/check-eligibility"
                className={buttonClasses("primary")}
                onClick={() => setMobileOpen(false)}
              >
                Find My Benefits
              </Link>
            </li>
          </ul>
        </nav>
      </header>

      <main id="main" tabIndex={-1} className="mx-auto w-full max-w-content flex-1 px-4 py-10 focus:outline-none">
        <Outlet />
      </main>

      <footer className="border-t border-border bg-surface">
        <div className="mx-auto flex max-w-content flex-col gap-2 px-4 py-6 text-sm text-muted">
          <p>
            Eligibility is an indication, not a government decision. Verify current rules with the official
            department or portal.
          </p>
          <p>This is an independent discovery platform, not a government website.</p>
        </div>
      </footer>
    </div>
  );
}
