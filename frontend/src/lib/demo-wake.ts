// Bounded read-only wake probes. Never retry login, entry or refresh mutations.
export async function waitForDemo(signal?: AbortSignal): Promise<void> {
  const deadline = Date.now() + 25000;
  for (let attempt = 0; attempt < 5 && Date.now() < deadline; attempt++) {
    signal?.throwIfAborted();
    try {
      const response = await fetch("/api/backend/health/ready", {
        cache: "no-store", credentials: "same-origin",
        signal: AbortSignal.any([AbortSignal.timeout(Math.max(1, Math.min(4000, deadline - Date.now()))), ...(signal ? [signal] : [])]),
      });
      if (response.ok && (await response.json()).status === "ok") return;
    } catch {
      signal?.throwIfAborted();
    }
    const remaining = deadline - Date.now();
    if (attempt < 4 && remaining > 0) await new Promise<void>((resolve) => setTimeout(resolve, Math.min(1500, remaining)));
  }
  throw new Error("The free demo may be waking or temporarily unavailable. Please retry in about 30 seconds.");
}
