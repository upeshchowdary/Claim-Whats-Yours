// Mirrors API_CONTRACT.md.

export interface HealthResponse {
  status: string;
  database?: string;
}

export interface Paginated<T> {
  items: T[];
  page: number;
  page_size: number;
  total: number;
}

export interface SchemeSummary {
  /** `id` is retained for compatibility with the documented public API. */
  id: string;
  /** Stable alias supplied by the current backend for client-side routes. */
  scheme_id: string;
  name: string;
  summary: string;
  government_level: string;
  scope: string;
  record_status: "published";
  verification_status: "verified" | "needs_review" | "stale" | string;
  last_verified_at: string | null;
  review_due_at?: string | null;
  current_version?: number;
  categories: string[];
  beneficiary_groups: string[];
}

export interface CriterionDetail {
  criterion_id: string | null;
  field: string;
  op: string;
  value: unknown;
  mandatory: boolean;
  explanation: string;
  source_refs: string[];
}

export interface DocumentRequirement {
  name?: string;
  title?: string;
  description?: string;
  mandatory?: boolean;
  source_refs?: string[];
}

export interface ApplicationStep {
  step?: number;
  instruction?: string;
  department?: string | null;
  office?: string | null;
}

export interface OfficialSource {
  id: string;
  source_id: string;
  title: string;
  publisher: string;
  url: string;
  source_type: string;
  official_status: string;
  access_date: string;
  retrieved_on: string;
  publication_date: string | null;
  section: string | null;
}

export interface SchemeDetail extends SchemeSummary {
  benefits: unknown[];
  documents: DocumentRequirement[];
  document_checklist: DocumentRequirement[];
  application_steps: ApplicationStep[];
  application_url: string | null;
  application_guidance: {
    steps: ApplicationStep[];
    application_url: string | null;
  };
  deadline: string | null;
  criteria: CriterionDetail[];
  sources: OfficialSource[];
  source_refs: OfficialSource[];
  jurisdictions: string[];
}

export interface EvaluateRequest {
  answers: Record<string, unknown>;
  filters?: {
    categories?: string[];
    government_levels?: string[];
  };
  locale?: string;
}

export interface CriterionResult {
  criterion_id: string;
  status: "PASS" | "FAIL" | "UNKNOWN";
  explanation: string;
  explanation_code?: string;
  source_refs: string[];
  mandatory: boolean;
}

export interface EvaluateResultItem {
  scheme_id?: string;
  name?: string;
  scheme?: SchemeSummary;
  decision: "LIKELY_ELIGIBLE" | "NEEDS_MORE_INFORMATION" | "NOT_LIKELY_ELIGIBLE" | "VERIFICATION_REQUIRED";
  verification_status: string;
  verification_current?: boolean;
  last_verified_at?: string | null;
  criteria: CriterionResult[];
  missing_fields: string[];
  follow_up_questions?: {
    field: string;
    label?: string;
    question_code?: string;
    input_type?: string;
    options?: { value: string; label: string }[];
    reason?: string;
  }[];
  document_checklist?: DocumentRequirement[];
  personalized_checklist?: {
    required: DocumentRequirement[];
    conditional: DocumentRequirement[];
    excluded: DocumentRequirement[];
    total_required: number;
    total_conditional: number;
    disclaimer: string;
  } | null;
  application_guidance?: {
    steps: ApplicationStep[];
    department: string | null;
    official_url: string | null;
    documents_needed: DocumentRequirement[];
    sources: { title: string | null; url: string | null; type: string | null }[];
  };
  source_refs?: string[];
  disclaimer?: string;
}

export interface EvaluateResponse {
  request_id?: string;
  evaluation_date: string;
  results: EvaluateResultItem[];
  excluded_schemes?: {
    scheme_id: string;
    name: string;
    reason: string;
    errors?: unknown[];
  }[];
  missing_fields: string[];
  follow_up_questions?: {
    field: string;
    label?: string;
    question_code?: string;
    input_type?: string;
    options?: { value: string; label: string }[];
    reason?: string;
  }[];
  coverage?: {
    schemes_considered: number;
    excluded_by_geography: number;
    excluded_by_filters: number;
  };
  disclaimer: string;
}

export interface AssistantTurnRequest {
  messages: string[];
  answers: Record<string, unknown>;
  locale?: string;
  scheme_ids?: string[];
}

export interface AssistantTurnResponse {
  follow_up_question: string | null;
  extracted_profile: Record<string, unknown>;
  missing_fields: string[];
  eligibility_ready: boolean;
  evaluation_suggestion: string | null;
}

export interface TrackingRecordResponse {
  tracking_id: string;
  token?: string;
  scheme_id?: string | null;
  status: string;
  progress_date?: string | null;
  reminder_date?: string | null;
  created_at?: string;
  updated_at?: string;
}
