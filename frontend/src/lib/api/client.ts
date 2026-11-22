import { ApiError, parseErrorBody } from "./errors";
import type {
  AssistantTurnRequest,
  AssistantTurnResponse,
  EvaluateRequest,
  EvaluateResponse,
  HealthResponse,
  Paginated,
  SchemeDetail,
  SchemeSummary,
  TrackingRecordResponse,
} from "./types";

// Use a same-origin path by default. This keeps the browser on Vite's development
// proxy locally and Nginx's reverse proxy in Docker/production; an explicit URL
// remains available only when VITE_API_BASE_URL is deliberately configured.
export const API_BASE_URL: string = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");

export async function apiGet<T>(path: string, init?: { signal?: AbortSignal }): Promise<T> {
  const requestId = crypto.randomUUID();
  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}${path}`, {
      method: "GET",
      headers: { Accept: "application/json", "X-Request-ID": requestId },
      signal: init?.signal,
    });
  } catch (cause) {
    if (init?.signal?.aborted) throw cause;
    throw new ApiError(0, "NETWORK_ERROR", "Network request failed.", requestId);
  }

  const responseRequestId = res.headers.get("X-Request-ID") ?? requestId;
  let body: unknown = null;
  try {
    body = await res.json();
  } catch {
    body = null;
  }

  if (!res.ok) {
    throw parseErrorBody(res.status, body, responseRequestId);
  }
  return body as T;
}

export async function apiPost<T>(
  path: string,
  bodyData: unknown,
  init?: { signal?: AbortSignal }
): Promise<T> {
  const requestId = crypto.randomUUID();
  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}${path}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
        "X-Request-ID": requestId,
      },
      body: JSON.stringify(bodyData),
      signal: init?.signal,
    });
  } catch (cause) {
    if (init?.signal?.aborted) throw cause;
    throw new ApiError(0, "NETWORK_ERROR", "Network request failed.", requestId);
  }

  const responseRequestId = res.headers.get("X-Request-ID") ?? requestId;
  let body: unknown = null;
  try {
    body = await res.json();
  } catch {
    body = null;
  }

  if (!res.ok) {
    throw parseErrorBody(res.status, body, responseRequestId);
  }
  return body as T;
}

export function health(): Promise<HealthResponse> {
  return apiGet<HealthResponse>("/health/live");
}

export function listSchemes(params?: URLSearchParams): Promise<Paginated<SchemeSummary>> {
  const query = params ? params.toString() : "";
  return apiGet<Paginated<SchemeSummary>>(`/api/v1/schemes${query ? `?${query}` : ""}`);
}

export function getScheme(id: string): Promise<SchemeDetail> {
  return apiGet<SchemeDetail>(`/api/v1/schemes/${encodeURIComponent(id)}`);
}

export function evaluateEligibility(req: EvaluateRequest): Promise<EvaluateResponse> {
  return apiPost<EvaluateResponse>("/api/v1/eligibility/evaluate", req);
}

export function assistantTurn(req: AssistantTurnRequest): Promise<AssistantTurnResponse> {
  return apiPost<AssistantTurnResponse>("/api/v1/assistant/turn", req);
}

export function createTracking(
  schemeId?: string | null,
  status: string = "planned",
  progressDate?: string | null,
  reminderDate?: string | null
): Promise<TrackingRecordResponse> {
  return apiPost<TrackingRecordResponse>("/api/v1/tracking", {
    scheme_id: schemeId,
    status,
    progress_date: progressDate,
    reminder_date: reminderDate,
  });
}
