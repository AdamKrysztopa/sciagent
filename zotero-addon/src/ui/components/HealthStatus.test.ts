import { describe, expect, it } from "vitest";

import { extractBackendHostname } from "./HealthStatus";

describe("extractBackendHostname", () => {
  it("extracts hostname from a Cloud Run URL", () => {
    expect(extractBackendHostname("https://sciagent-ewpafdgfya-ew.a.run.app")).toBe(
      "sciagent-ewpafdgfya-ew.a.run.app",
    );
  });

  it("includes port for localhost", () => {
    expect(extractBackendHostname("http://localhost:57321")).toBe("localhost:57321");
  });

  it("includes port for 127.0.0.1", () => {
    expect(extractBackendHostname("http://127.0.0.1:8000")).toBe("127.0.0.1:8000");
  });

  it("omits default port 443 for https", () => {
    expect(extractBackendHostname("https://api.example.com")).toBe("api.example.com");
  });

  it("falls back to the raw string for an unparseable URL", () => {
    expect(extractBackendHostname("not-a-url")).toBe("not-a-url");
  });

  it("defaults to 127.0.0.1:8000 for empty string", () => {
    expect(extractBackendHostname("")).toBe("127.0.0.1:8000");
  });
});
