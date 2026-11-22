import { describe, it, expect } from "vitest";
import { parseErrorBody, userMessageForCode } from "./errors";

describe("parseErrorBody", () => {
  it("reads code and message from the error envelope", () => {
    const err = parseErrorBody(404, { error: { code: "SCHEME_NOT_FOUND", message: "Scheme not found" } }, "req-1");
    expect(err.status).toBe(404);
    expect(err.code).toBe("SCHEME_NOT_FOUND");
    expect(err.message).toBe("Scheme not found");
    expect(err.requestId).toBe("req-1");
  });

  it("falls back to HTTP_ERROR when the body has no envelope", () => {
    const err = parseErrorBody(500, "<html>oops</html>", null);
    expect(err.code).toBe("HTTP_ERROR");
  });
});

describe("userMessageForCode", () => {
  it("returns the default message for an unknown code", () => {
    expect(userMessageForCode("SOMETHING_UNEXPECTED")).toBe("Something went wrong. Please try again.");
  });
});
