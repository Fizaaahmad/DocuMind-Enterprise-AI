import { afterEach, expect, it, vi } from "vitest";
import { api, ApiError } from "./api";

afterEach(() => vi.unstubAllGlobals());
const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status });

it("fetches a CSRF token before login and uses same-origin cookie transport", async () => {
  const fetcher = vi
    .fn()
    .mockResolvedValueOnce(json({ csrf_token: "signed-csrf" }))
    .mockResolvedValueOnce(json({ id: "user" }));
  vi.stubGlobal("fetch", fetcher);
  await api("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email: "alice@example.com", password: "test" }),
  });
  expect(fetcher.mock.calls[0][0]).toBe("/api/backend/auth/csrf");
  const init = fetcher.mock.calls[1][1];
  expect(init.credentials).toBe("same-origin");
  expect(init.headers.get("x-csrf-token")).toBe("signed-csrf");
  expect(init.headers.get("authorization")).toBeNull();
});

it("coordinates concurrent expired requests through one refresh", async () => {
  let renewed = false;
  let refreshes = 0;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      if (url.endsWith("/auth/csrf")) return json({ csrf_token: "csrf" });
      if (url.endsWith("/auth/me")) return json({ detail: "expired" }, 401);
      if (url.endsWith("/auth/refresh")) {
        refreshes++;
        renewed = true;
        return json({ status: "ok" });
      }
      return renewed ? json([]) : json({ detail: "expired" }, 401);
    }),
  );
  expect(
    await Promise.all([api("/organizations"), api("/organizations")]),
  ).toEqual([[], []]);
  expect(refreshes).toBe(1);
});

it("returns authentication errors when refresh is rejected", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) =>
      url.endsWith("/auth/csrf")
        ? json({ csrf_token: "csrf" })
        : json({ detail: "Session expired" }, 401),
    ),
  );
  await expect(api("/organizations")).rejects.toMatchObject({
    status: 401,
    message: "Session expired",
  });
});

it("does not refresh on authorization errors", async () => {
  const fetcher = vi
    .fn()
    .mockResolvedValue(json({ detail: "Admin required" }, 403));
  vi.stubGlobal("fetch", fetcher);
  await expect(api("/organizations/example")).rejects.toBeInstanceOf(ApiError);
  expect(fetcher).toHaveBeenCalledTimes(1);
});

it("handles unavailable services and validation errors", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("network")));
  await expect(api("/organizations")).rejects.toMatchObject({ status: 0 });
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockResolvedValue(json({ detail: [{ msg: "Name required" }] }, 422)),
  );
  await expect(api("/organizations")).rejects.toThrow("Name required");
});
