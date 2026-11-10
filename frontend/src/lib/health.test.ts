import { afterEach, describe, expect, it, vi } from "vitest";
import { fetchHealth } from "./health";

afterEach(() => vi.unstubAllGlobals());

describe("fetchHealth", () => {
  it("reports operational services", async () => {
    vi.stubGlobal("fetch", vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ status: "ok" })))
      .mockResolvedValueOnce(new Response(JSON.stringify({ status: "ok", database: "ok", pgvector: "ok" }))));
    expect(await fetchHealth()).toEqual({ api: "ok", database: "ok", pgvector: "ok" });
  });

  it("preserves database status from a 503 readiness response", async () => {
    vi.stubGlobal("fetch", vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ status: "ok" })))
      .mockResolvedValueOnce(new Response(JSON.stringify({ status: "degraded", database: "ok", pgvector: "unavailable" }), { status: 503 })));
    expect(await fetchHealth()).toEqual({ api: "ok", database: "ok", pgvector: "unavailable" });
  });

  it("handles network failures", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    expect(await fetchHealth()).toEqual({ api: "unavailable", database: "unavailable", pgvector: "unavailable" });
  });

  it("handles invalid JSON and unexpected responses", async () => {
    vi.stubGlobal("fetch", vi.fn()
      .mockResolvedValueOnce(new Response("invalid"))
      .mockResolvedValueOnce(new Response("error", { status: 500 })));
    expect(await fetchHealth()).toEqual({ api: "unavailable", database: "unavailable", pgvector: "unavailable" });
  });
});
