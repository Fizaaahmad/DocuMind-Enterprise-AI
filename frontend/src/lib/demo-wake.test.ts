import { afterEach, expect, it, vi } from "vitest";
import { waitForDemo } from "./demo-wake";

afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers(); });

it("uses only short read-only health calls and accepts readiness", async () => {
  const fetcher = vi.fn().mockResolvedValue(Response.json({ status: "ok" }));
  vi.stubGlobal("fetch", fetcher);
  await waitForDemo();
  expect(fetcher).toHaveBeenCalledTimes(1);
  expect(fetcher.mock.calls[0][0]).toBe("/api/backend/health/ready");
  expect(fetcher.mock.calls[0][1].method).toBeUndefined();
});

it("bounds unavailable checks without retrying mutations", async () => {
  vi.useFakeTimers();
  const fetcher = vi.fn().mockRejectedValue(new Error("sleeping"));
  vi.stubGlobal("fetch", fetcher);
  const check = expect(waitForDemo()).rejects.toThrow("retry in about 30 seconds");
  await vi.advanceTimersByTimeAsync(25000);
  await check;
  expect(fetcher).toHaveBeenCalledTimes(5);
});

it("honors cancellation", async () => {
  const controller = new AbortController(); controller.abort();
  const fetcher = vi.fn(); vi.stubGlobal("fetch", fetcher);
  await expect(waitForDemo(controller.signal)).rejects.toThrow();
  expect(fetcher).not.toHaveBeenCalled();
});
