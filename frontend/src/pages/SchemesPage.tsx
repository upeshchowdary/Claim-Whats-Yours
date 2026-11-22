import { useState, type ChangeEvent, type FormEvent } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";
import { Card } from "../components/ui/Card";
import { Input } from "../components/ui/Input";
import { Select } from "../components/ui/Select";
import { StatusBadge } from "../components/ui/StatusBadge";
import { Skeleton } from "../components/ui/Skeleton";
import { ErrorState } from "../components/ui/ErrorState";
import { EmptyState } from "../components/ui/EmptyState";
import { listSchemes } from "../lib/api/client";

const GOVT_LEVELS = [
  { value: "", label: "All Levels" },
  { value: "central", label: "Central Government" },
  { value: "state", label: "State Government" },
  { value: "ut", label: "Union Territory" },
  { value: "district", label: "District Level" },
];

export function SchemesPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [q, setQ] = useState(searchParams.get("q") ?? "");
  const govtLevel = searchParams.get("government_level") ?? "";

  const queryParams = new URLSearchParams();
  if (q.trim()) queryParams.set("q", q.trim());
  if (govtLevel) queryParams.set("government_level", govtLevel);

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["schemes", queryParams.toString()],
    queryFn: () => listSchemes(queryParams),
  });

  const handleSearchSubmit = (e: FormEvent) => {
    e.preventDefault();
    const newParams = new URLSearchParams(searchParams);
    if (q.trim()) {
      newParams.set("q", q.trim());
    } else {
      newParams.delete("q");
    }
    setSearchParams(newParams);
  };

  const handleLevelChange = (e: ChangeEvent<HTMLSelectElement>) => {
    const val = e.target.value;
    const newParams = new URLSearchParams(searchParams);
    if (val) {
      newParams.set("government_level", val);
    } else {
      newParams.delete("government_level");
    }
    setSearchParams(newParams);
  };

  return (
    <div className="flex flex-col gap-8">
      <div>
        <h1 className="text-3xl font-bold text-foreground">Explore Government Schemes</h1>
        <p className="mt-2 text-muted">
          Browse verified central and state welfare programs designed to support citizens.
        </p>
      </div>

      {/* Filter controls */}
      <form onSubmit={handleSearchSubmit} className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <div className="md:col-span-2">
          <Input
            id="scheme-search"
            label="Search schemes"
            placeholder="Search by scheme name or keyword..."
            value={q}
            onChange={(e: ChangeEvent<HTMLInputElement>) => setQ(e.target.value)}
          />
        </div>
        <div>
          <Select
            id="govt-level"
            label="Government Level"
            value={govtLevel}
            onChange={handleLevelChange}
            options={GOVT_LEVELS}
          />
        </div>
      </form>

      {/* Loading state */}
      {isLoading && (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <Skeleton className="h-40 w-full" />
          <Skeleton className="h-40 w-full" />
          <Skeleton className="h-40 w-full" />
          <Skeleton className="h-40 w-full" />
        </div>
      )}

      {/* Error state */}
      {isError && (
        <ErrorState
          message={error instanceof Error ? error.message : "Failed to connect to backend server."}
          onRetry={() => refetch()}
        />
      )}

      {/* Results */}
      {data && (
        <>
          <p className="text-sm text-muted">
            Showing {data.items.length} of {data.total} scheme(s)
          </p>

          {data.items.length === 0 ? (
            <EmptyState
              title="No schemes found"
              description="Try adjusting your search criteria or filters."
            />
          ) : (
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              {data.items.map((scheme) => (
                <Card key={scheme.scheme_id} className="card-lift flex flex-col justify-between gap-4">
                  <div className="flex flex-col gap-2">
                    <div className="flex items-start justify-between gap-2">
                      <h2 className="text-lg font-bold text-foreground">{scheme.name}</h2>
                      <StatusBadge status={scheme.verification_status ?? "verified"} />
                    </div>
                    <p className="text-sm text-muted line-clamp-3">{scheme.summary || ""}</p>
                  </div>

                  <div className="flex items-center justify-between border-t border-border pt-3 text-xs text-muted">
                    <span className="capitalize">{scheme.government_level || "Government"} Level</span>
                    <Link
                      to={`/schemes/${encodeURIComponent(scheme.scheme_id)}`}
                      className="font-semibold text-primary hover:text-primary-dark"
                    >
                      View Details &rarr;
                    </Link>
                  </div>
                </Card>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
