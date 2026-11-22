import { useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Card } from "../components/ui/Card";
import { StatusBadge } from "../components/ui/StatusBadge";
import { Skeleton } from "../components/ui/Skeleton";
import { ErrorState } from "../components/ui/ErrorState";
import { buttonClasses } from "../components/ui/Button";
import { getScheme } from "../lib/api/client";

export function SchemeDetailPage() {
  const { id } = useParams<{ id: string }>();

  const { data: scheme, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["scheme", id],
    queryFn: () => getScheme(id ?? ""),
    enabled: Boolean(id),
  });

  if (isLoading) {
    return (
      <div className="flex flex-col gap-6">
        <Skeleton className="h-10 w-2/3" />
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-48 w-full" />
      </div>
    );
  }

  if (isError || !scheme) {
    return (
      <ErrorState
        message={error instanceof Error ? error.message : "The requested scheme could not be retrieved."}
        onRetry={() => refetch()}
      />
    );
  }

  return (
    <div className="flex flex-col gap-8">
      <Link to="/schemes" className="text-sm font-semibold text-primary hover:underline">
        &larr; Back to all schemes
      </Link>

      <div className="flex flex-col gap-3">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <h1 className="text-3xl font-bold text-foreground">{scheme.name}</h1>
          <StatusBadge status={scheme.verification_status ?? "verified"} />
        </div>
        <p className="text-lg text-muted">{scheme.summary}</p>
        <div className="flex flex-wrap gap-2 pt-2">
          {scheme.government_level && (
            <span className="rounded-full bg-primary-soft px-3 py-1 text-xs font-semibold text-primary capitalize">
              {scheme.government_level} Government
            </span>
          )}
          {scheme.categories?.map((cat) => (
            <span key={cat} className="rounded-full bg-surface-alt px-3 py-1 text-xs text-muted">
              {cat}
            </span>
          ))}
        </div>
      </div>

      {/* Action shortcuts */}
      <div className="flex flex-wrap gap-4">
        {scheme.application_guidance?.application_url && (
          <a
            href={scheme.application_guidance.application_url}
            target="_blank"
            rel="noopener noreferrer"
            className={buttonClasses("primary")}
          >
            Apply via Official Portal &nearr;
          </a>
        )}
        <Link to="/check-eligibility" className={buttonClasses("secondary")}>
          Check My Eligibility
        </Link>
      </div>

      {/* Criteria */}
      {scheme.criteria && scheme.criteria.length > 0 && (
        <Card className="flex flex-col gap-4">
          <h2 className="text-xl font-bold text-foreground">Eligibility Criteria</h2>
          <ul className="divide-y divide-border">
            {scheme.criteria.map((c, i) => (
              <li key={c.criterion_id ?? i} className="py-3 flex flex-col gap-2">
                <div className="flex items-center justify-between gap-4">
                  <span className="text-sm font-semibold text-foreground">{c.explanation}</span>
                  {c.mandatory && (
                    <span className="text-xs bg-danger-soft text-danger px-2 py-0.5 rounded font-medium">
                      Mandatory
                    </span>
                  )}
                </div>
                <span className="text-xs text-muted">
                  {c.field} · {c.op} {String(c.value)}
                </span>
              </li>
            ))}
          </ul>
        </Card>
      )}

      {scheme.document_checklist.length > 0 && (
        <Card className="flex flex-col gap-3">
          <h2 className="text-lg font-bold text-foreground">Documents You May Need</h2>
          <ul className="list-disc pl-5 text-sm text-muted flex flex-col gap-2">
            {scheme.document_checklist.map((document, i) => (
              <li key={`${document.name ?? document.title ?? "document"}-${i}`}>
                <span className="font-medium text-foreground">{document.name ?? document.title ?? "Document"}</span>
                {document.description ? ` — ${document.description}` : ""}
                {document.mandatory === false ? " (confirm whether this applies to you)" : ""}
              </li>
            ))}
          </ul>
        </Card>
      )}

      {scheme.application_guidance.steps.length > 0 && (
        <Card className="flex flex-col gap-3">
          <h2 className="text-lg font-bold text-foreground">How to Apply</h2>
          <ol className="list-decimal pl-5 text-sm text-muted flex flex-col gap-3">
            {scheme.application_guidance.steps.map((step, i) => (
              <li key={step.step ?? i}>
                <span className="text-foreground">{step.instruction ?? "Follow the official application process."}</span>
                {step.department ? <span className="block text-xs">Department: {step.department}</span> : null}
              </li>
            ))}
          </ol>
        </Card>
      )}

      <Card className="flex flex-col gap-3">
        <h2 className="text-lg font-bold text-foreground">Official Sources & References</h2>
        <ul className="list-disc pl-5 text-sm text-muted flex flex-col gap-1">
          {scheme.source_refs.map((src) => (
            <li key={src.source_id}>
              <a
                href={src.url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-primary hover:underline"
              >
                {src.title}
              </a>
              {src.section ? <span> — {src.section}</span> : null}
            </li>
          ))}
        </ul>
      </Card>

      <p className="text-xs text-muted border-t border-border pt-4">
        Eligibility is an indication, not a government decision. Always verify current requirements using the official sources above.
      </p>
    </div>
  );
}
