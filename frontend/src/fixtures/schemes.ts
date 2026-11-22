import type { SchemeSummary } from "../lib/api/types";

export const DEMO_DATA_NOTICE = "Demo data for development only. Not real government information.";

const demoScheme = (
  id: string,
  name: string,
  summary: string,
  governmentLevel: string,
  verificationStatus: string
): SchemeSummary => ({
  id,
  scheme_id: id,
  name,
  summary,
  government_level: governmentLevel,
  scope: governmentLevel === "central" ? "all_india" : "state",
  record_status: "published",
  verification_status: verificationStatus,
  last_verified_at: null,
  categories: [],
  beneficiary_groups: [],
});

export const DEMO_SCHEMES: SchemeSummary[] = [
  demoScheme(
    "demo-scheme-1",
    "[DEMO] Sample Housing Support Scheme",
    "Placeholder summary used only to demonstrate layout.",
    "state",
    "unverified"
  ),
  demoScheme(
    "demo-scheme-2",
    "[DEMO] Sample Education Grant",
    "Placeholder summary used only to demonstrate layout.",
    "central",
    "pending"
  ),
  demoScheme(
    "demo-scheme-3",
    "[DEMO] Sample Health Cover Scheme",
    "Placeholder summary used only to demonstrate layout.",
    "central",
    "verified"
  ),
];
