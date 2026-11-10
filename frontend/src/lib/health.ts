export type ServiceStatus = "ok" | "unavailable";
export type HealthSnapshot = {
  api: ServiceStatus;
  database: ServiceStatus;
  pgvector: ServiceStatus;
};

const apiUrl = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

async function check(path: string) {
  try {
    const response = await fetch(`${apiUrl}/api/v1/${path}`, {
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
