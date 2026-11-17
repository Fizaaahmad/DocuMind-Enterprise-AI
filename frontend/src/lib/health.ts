export type ServiceStatus = "ok" | "unavailable";
export type HealthSnapshot = {
  api: ServiceStatus;
  database: ServiceStatus;
  pgvector: ServiceStatus;
};

// Keep status available when FastAPI is private behind the frontend.
const apiUrl = "/api/backend";

async function check(path: string) {
  try {
    const response = await fetch(`${apiUrl}/${path}`, {
      cache: "no-store",
      signal: AbortSignal.timeout(5000),
    });
    // Readiness intentionally returns a JSON status body with HTTP 503.
    if (!response.ok && response.status !== 503) return null;
    const body: unknown = await response.json();
    return typeof body === "object" && body !== null ? body as Record<string, unknown> : null;
  } catch {
    return null;
  }
}

export async function fetchHealth(): Promise<HealthSnapshot> {
  const [live, ready] = await Promise.all([check("health"), check("health/ready")]);
  return {
    api: live?.status === "ok" ? "ok" : "unavailable",
    database: ready?.database === "ok" ? "ok" : "unavailable",
    pgvector: ready?.pgvector === "ok" ? "ok" : "unavailable",
  };
}
