export type ApiErrorCode =
  | "BAD_REQUEST"
  | "VALIDATION_ERROR"
  | "SCHEME_NOT_FOUND"
  | "RATE_LIMITED"
  | "INTERNAL_ERROR"
  | "NOT_FOUND"
  | "HTTP_ERROR"
  | "INVALID_QUERY"
  | "UNKNOWN_PROFILE_FIELD"
  | (string & {});

export class ApiError extends Error {
  status: number;
  code: string;
  requestId: string | null;

  constructor(status: number, code: string, message: string, requestId: string | null = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.requestId = requestId;
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

export function parseErrorBody(status: number, body: unknown, requestId: string | null): ApiError {
  const envelope = isRecord(body) && isRecord(body.error) ? body.error : null;
  const code = envelope && typeof envelope.code === "string" ? envelope.code : "HTTP_ERROR";
  const message =
    envelope && typeof envelope.message === "string"
      ? envelope.message
      : `Request failed with status ${status}.`;
  return new ApiError(status, code, message, requestId);
}

const USER_MESSAGES = new Map<string, string>([
  ["BAD_REQUEST", "Something in your request was not valid. Please check it and try again."],
  ["VALIDATION_ERROR", "Some answers need a second look. Please check the highlighted fields."],
  ["SCHEME_NOT_FOUND", "We could not find this scheme. It may have been removed or the link is incorrect."],
  ["RATE_LIMITED", "Too many requests. Please wait a moment and try again."],
  ["INTERNAL_ERROR", "Something went wrong on our side. Please try again in a few minutes."],
  ["NOT_FOUND", "We could not find what you asked for."],
  ["INVALID_QUERY", "Your search or filter could not be understood. Please adjust it and try again."],
  ["UNKNOWN_PROFILE_FIELD", "One of the answers was not recognised. Please refresh and try again."],
  ["NETWORK_ERROR", "We could not reach the service. Check your connection and try again."],
]);

const DEFAULT_USER_MESSAGE = "Something went wrong. Please try again.";

export function userMessageForCode(code: string): string {
  return USER_MESSAGES.get(code) ?? DEFAULT_USER_MESSAGE;
}
