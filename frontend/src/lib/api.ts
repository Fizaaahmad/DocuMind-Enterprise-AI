export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

const prefix = "/api/backend";
let refreshPromise: Promise<void> | null = null;

async function request(
  path: string,
  init: RequestInit = {},
): Promise<Response> {
  const headers = new Headers(init.headers);
  const method = init.method ?? "GET";
  if (!["GET", "HEAD"].includes(method)) {
    const csrf = await fetch(`${prefix}/auth/csrf`, {
      cache: "no-store",
      credentials: "same-origin",
    });
    if (!csrf.ok)
      throw new ApiError(
        csrf.status,
        "Unable to secure request. Please try again.",
      );
    const { csrf_token } = await csrf.json();
    headers.set("X-CSRF-Token", csrf_token);
    headers.set("Content-Type", "application/json");
  }
  return fetch(`${prefix}${path}`, {
    ...init,
    headers,
    credentials: "same-origin",
    cache: "no-store",
    signal: init.signal ?? AbortSignal.timeout(15000),
  });
}

async function failure(response: Response): Promise<never> {
  let message = "The request could not be completed. Please try again.";
  try {
    const body = await response.json();
    if (typeof body.detail === "string") message = body.detail;
    else if (Array.isArray(body.detail))
      message = body.detail.map((e: { msg: string }) => e.msg).join(". ");
  } catch {
    /* Unavailable upstream may not return JSON. */
  }
  throw new ApiError(response.status, message);
}

export async function refreshSession(): Promise<void> {
  if (!refreshPromise) {
    refreshPromise = (async () => {
      // Serialize refresh across tabs where Web Locks is available. Recheck access
      // inside the lock: another tab may already have rotated the shared cookie.
      const refresh = async () => {
        if ((await request("/auth/me")).ok) return;
        const response = await request("/auth/refresh", { method: "POST" });
        if (!response.ok) await failure(response);
      };
      if (typeof navigator !== "undefined" && navigator.locks) {
        await navigator.locks.request("documind-refresh", refresh);
      } else await refresh();
    })().finally(() => {
      refreshPromise = null;
    });
  }
  return refreshPromise;
}

export async function apiResponse(
  path: string,
  init: RequestInit = {},
): Promise<Response> {
  try {
    let response = await request(path, init);
    if (response.status === 401 && !path.startsWith("/auth/")) {
      await refreshSession();
      response = await request(path, init);
    }
    if (!response.ok) return failure(response);
    return response;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    throw new ApiError(
      0,
      "Cannot reach DocuMind. Check your connection and try again.",
    );
  }
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await apiResponse(path, init);
  if (response.status === 204) return undefined as T;
  try {
    return await response.json();
  } catch {
    throw new ApiError(
      0,
      "DocuMind returned an invalid response. Please try again.",
    );
  }
}
