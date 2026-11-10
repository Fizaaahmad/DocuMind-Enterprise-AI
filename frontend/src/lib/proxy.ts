// Server-only transport. Do not import this module into client components.
export async function proxyRequest(
  request: Request,
  segments: string[],
): Promise<Response> {
  const path = segments.join("/");
  const auth = /^auth\/(csrf|register|login|refresh|logout|me)$/;
  const orgs =
    /^organizations(?:\/[0-9a-f-]{36}(?:\/members(?:\/[0-9a-f-]{36})?)?)?$/i;
  if (!auth.test(path) && !orgs.test(path))
    return new Response(null, { status: 404 });
  const headers = new Headers();
  for (const key of ["cookie", "origin", "content-type", "x-csrf-token"]) {
    const value = request.headers.get(key);
    if (value) headers.set(key, value);
  }
  try {
    const body = ["GET", "HEAD"].includes(request.method)
      ? undefined
      : await request.text();
    if (body && new TextEncoder().encode(body).length > 16384)
      return new Response(null, { status: 413 });
    const response = await fetch(
      `${process.env.BACKEND_URL ?? "http://127.0.0.1:8000"}/api/v1/${path}`,
      {
        method: request.method,
        headers,
        body,
        cache: "no-store",
        redirect: "manual",
        signal: AbortSignal.timeout(10000),
      },
    );
    const outgoing = new Headers({
      "Cache-Control": "no-store",
      "X-Content-Type-Options": "nosniff",
    });
    outgoing.set(
      "Content-Type",
      response.headers.get("content-type") ?? "application/json",
    );
    for (const cookie of response.headers.getSetCookie())
      outgoing.append("Set-Cookie", cookie);
    return new Response(response.body, {
      status: response.status,
      headers: outgoing,
    });
  } catch {
    return Response.json(
      { detail: "Backend unavailable. Please try again." },
      { status: 502 },
    );
  }
}
