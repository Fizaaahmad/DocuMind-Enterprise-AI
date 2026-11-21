import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import type { User } from "./types";

export async function requireUser(next = "/dashboard"): Promise<User> {
  const wake = () => {
    const allowed = ["/dashboard", "/documents", "/assistant", "/intelligence", "/operations"];
    redirect(`/demo-wake?next=${encodeURIComponent(allowed.includes(next) ? next : "/dashboard")}`);
  };
  const jar = await cookies();
  const cookie = jar.toString();
  let response: Response;
  try {
    response = await fetch(
      `${process.env.BACKEND_URL ?? "http://127.0.0.1:8000"}/api/v1/auth/me`,
      {
        headers: { cookie },
        cache: "no-store",
        signal: AbortSignal.timeout(10000),
      },
    );
  } catch {
    if (process.env.DEMO_MODE === "true") wake();
    throw new Error(
      "DocuMind backend is unavailable. Please try again shortly.",
    );
  }
  if (response.status === 401) {
    // Server components cannot set cookies. A dedicated client page performs the
    // CSRF-protected POST refresh, then re-enters this guard with updated cookies.
    const hasRefresh = jar.has("dm_refresh") || jar.has("__Host-dm_refresh");
    redirect(hasRefresh ? "/session" : "/login");
  }
  if (process.env.DEMO_MODE === "true" && (
    [502, 503, 504].includes(response.status) ||
    (response.ok && !response.headers.get("content-type")?.includes("application/json"))
  )) wake();
  if (!response.ok) throw new Error("Unable to verify your DocuMind session.");
  return response.json();
}
