import { afterEach, expect, it, vi } from "vitest";
import { proxyRequest } from "./proxy";

afterEach(() => vi.unstubAllGlobals());

it("forwards origin, CSRF and cookies and preserves individual Set-Cookie headers", async () => {
  const headers = new Headers({ "Content-Type": "application/json" });
  headers.append(
    "Set-Cookie",
    "dm_access=token; HttpOnly; Path=/; SameSite=Lax",
  );
  headers.append(
    "Set-Cookie",
    "dm_refresh=token; HttpOnly; Path=/; SameSite=Lax",
  );
  const fetcher = vi.fn().mockResolvedValue(new Response("{}", { headers }));
  vi.stubGlobal("fetch", fetcher);
  const request = new Request("http://localhost:3000/api/backend/auth/login", {
    method: "POST",
    headers: {
      Origin: "http://localhost:3000",
      "X-CSRF-Token": "csrf",
      Cookie: "dm_csrf=csrf",
      Authorization: "untrusted",
    },
    body: "{}",
  });
  const response = await proxyRequest(request, ["auth", "login"]);
  const forwarded = fetcher.mock.calls[0][1].headers;
  expect(forwarded.get("origin")).toBe("http://localhost:3000");
  expect(forwarded.get("x-csrf-token")).toBe("csrf");
  expect(forwarded.get("authorization")).toBeNull();
  expect(response.headers.getSetCookie()).toHaveLength(2);
  expect(response.headers.get("cache-control")).toBe("no-store");
});

it("rejects paths outside the explicit API allowlist", async () => {
  const fetcher = vi.fn();
  vi.stubGlobal("fetch", fetcher);
  expect(
    (await proxyRequest(new Request("http://localhost"), ["..", "admin"]))
      .status,
  ).toBe(404);
  expect(fetcher).not.toHaveBeenCalled();
});

it("returns a sanitized unavailable response", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockRejectedValue(new Error("private upstream details")),
  );
  const response = await proxyRequest(new Request("http://localhost"), [
    "auth",
    "me",
  ]);
  expect(response.status).toBe(502);
  expect(await response.text()).not.toContain("private upstream details");
});
