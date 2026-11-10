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

it("streams multipart uploads after checking organization access and backend limits", async () => {
  const org = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
  let received = "";
  const fetcher = vi.fn(async (_url: string, init?: RequestInit) => {
    if (_url.endsWith("/config"))
      return Response.json({ upload_max_bytes: 20971520 });
    received = await new Response(init?.body).text();
    return Response.json({ id: "doc", status: "pending" }, { status: 202 });
  });
  vi.stubGlobal("fetch", fetcher);
  const boundary = "documind-test-boundary";
  const multipart = `--${boundary}\r\nContent-Disposition: form-data; name="file"; filename="notes.txt"\r\nContent-Type: text/plain\r\n\r\nsource text\r\n--${boundary}--\r\n`;
  const request = new Request(
    `http://localhost:3000/api/backend/organizations/${org}/documents`,
    {
      method: "POST",
      body: multipart,
      headers: {
        Cookie: "dm_access=opaque",
        "X-CSRF-Token": "signed",
        "Content-Type": `multipart/form-data; boundary=${boundary}`,
      },
    },
  );
  const response = await proxyRequest(request, [
    "organizations",
    org,
    "documents",
  ]);
  expect(response.status).toBe(202);
  expect(received).toContain("source text");
  expect(received).toContain("notes.txt");
  expect(fetcher).toHaveBeenCalledTimes(2);
});

it("does not forward an upload when organization authorization fails", async () => {
  const org = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
  const fetcher = vi
    .fn()
    .mockResolvedValue(
      Response.json({ detail: "Organization not found" }, { status: 404 }),
    );
  vi.stubGlobal("fetch", fetcher);
  const request = new Request("http://localhost/upload", {
    method: "POST",
    body: "file",
  });
  expect(
    (await proxyRequest(request, ["organizations", org, "documents"])).status,
  ).toBe(404);
  expect(fetcher).toHaveBeenCalledTimes(1);
});

it("preserves document filters and attachment headers", async () => {
  const org = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
  const fetcher = vi.fn().mockResolvedValue(
    new Response("data", {
      headers: { "Content-Disposition": "attachment; filename=notes.txt" },
    }),
  );
  vi.stubGlobal("fetch", fetcher);
  const response = await proxyRequest(
    new Request("http://localhost/documents?q=notes&status=completed"),
    ["organizations", org, "documents"],
  );
  expect(fetcher.mock.calls[0][0]).toContain("?q=notes&status=completed");
  expect(response.headers.get("content-disposition")).toContain("attachment");
});

it("bounds streamed uploads even without Content-Length", async () => {
  const org = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
  const fetcher = vi.fn(async (url: string, init?: RequestInit) => {
    if (url.endsWith("/config"))
      return Response.json({ upload_max_bytes: 1024 });
    await new Response(init?.body).text();
    return Response.json({});
  });
  vi.stubGlobal("fetch", fetcher);
  const response = await proxyRequest(
    new Request("http://localhost/upload", {
      method: "POST",
      body: "x".repeat(70000),
    }),
    ["organizations", org, "documents"],
  );
  expect(response.status).toBe(413);
});
