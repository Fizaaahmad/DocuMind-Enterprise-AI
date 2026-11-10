import { afterEach, expect, it, vi } from "vitest";
import { requireUser } from "./server-auth";

const { jar, redirect } = vi.hoisted(() => ({
  jar: { toString: vi.fn(), has: vi.fn() },
  redirect: vi.fn((path: string) => {
    throw new Error(`redirect:${path}`);
  }),
}));
vi.mock("next/headers", () => ({ cookies: async () => jar }));
vi.mock("next/navigation", () => ({ redirect }));
afterEach(() => {
  vi.unstubAllGlobals();
  vi.clearAllMocks();
});

it("validates cookies with FastAPI before rendering user data", async () => {
  jar.toString.mockReturnValue("dm_access=opaque");
  const fetcher = vi
    .fn()
    .mockResolvedValue(Response.json({ id: "user", name: "Alice" }));
  vi.stubGlobal("fetch", fetcher);
  expect(await requireUser()).toMatchObject({ id: "user" });
  expect(fetcher.mock.calls[0][1]).toMatchObject({
    headers: { cookie: "dm_access=opaque" },
    cache: "no-store",
  });
});

it("redirects missing authentication to login", async () => {
  jar.has.mockReturnValue(false);
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(new Response(null, { status: 401 })),
  );
  await expect(requireUser()).rejects.toThrow("redirect:/login");
});

it("routes expired access through a POST refresh page when refresh cookies exist", async () => {
  jar.has.mockImplementation((name) => name === "__Host-dm_refresh");
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(new Response(null, { status: 401 })),
  );
  await expect(requireUser()).rejects.toThrow("redirect:/session");
});

it("fails closed when the backend is unavailable", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("network")));
  await expect(requireUser()).rejects.toThrow("backend is unavailable");
});
