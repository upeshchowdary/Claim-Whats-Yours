import { Link } from "react-router-dom";
import { buttonClasses } from "../components/ui/Button";

export function NotFoundPage() {
  return (
    <section className="flex flex-col items-start gap-4">
      <h1 className="text-3xl font-bold text-foreground">Page not found</h1>
      <p className="text-muted">The page you are looking for does not exist or has moved.</p>
      <Link to="/" className={buttonClasses("primary")}>
        Back to home
      </Link>
    </section>
  );
}
