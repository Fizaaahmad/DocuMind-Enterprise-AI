// Server-only transport. Do not import this module into client components.
export async function proxyRequest(
  request: Request,
  segments: string[],
): Promise<Response> {
  const path = segments.join("/");
  const auth = /^auth\/(csrf|register|login|refresh|logout|me)$/;
  const orgs =
    /^organizations(?:\/[0-9a-f-]{36}(?:\/members(?:\/[0-9a-f-]{36})?)?)?$/i;
  const documents =
    /^organizations\/[0-9a-f-]{36}\/documents(?:\/(?:config|[0-9a-f-]{36}(?:\/(?:content|download|retry))?))?$/i;
  if (!auth.test(path) && !orgs.test(path) && !documents.test(path))
    return new Response(null, { status: 404 });
  const headers = new Headers();
  for (const key of ["cookie", "origin", "content-type", "x-csrf-token"]) {
    const value = request.headers.get(key);
    if (value) headers.set(key, value);
  }
  const backend = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";
  const upload =
    request.method === "POST" &&
    /^organizations\/[0-9a-f-]{36}\/documents$/i.test(path);
  let tooLarge = false;
  const outgoingResponse = (response: Response) => {
    const outgoing = new Headers({
      "Cache-Control": "no-store",
      "X-Content-Type-Options": "nosniff",
    });
    for (const key of [
      "content-type",
      "content-disposition",
      "content-length",
    ]) {
      const value = response.headers.get(key);
      if (value) outgoing.set(key, value);
    }
    for (const cookie of response.headers.getSetCookie())
      outgoing.append("Set-Cookie", cookie);
    return new Response(response.body, {
      status: response.status,
      headers: outgoing,
    });
  };
  try {
    let limit = 16384;
    if (upload) {
      // Authorize the organization and discover the backend's authoritative limit
      // before forwarding a potentially large request body.
      const config = await fetch(`${backend}/api/v1/${path}/config`, {
        headers: { cookie: headers.get("cookie") ?? "" },
        cache: "no-store",
        redirect: "manual",
        signal: AbortSignal.timeout(10000),
      });
      if (!config.ok) return outgoingResponse(config);
      const { upload_max_bytes } = await config.json();
      if (
        !Number.isSafeInteger(upload_max_bytes) ||
        upload_max_bytes < 1024 ||
        upload_max_bytes > 200 * 1024 * 1024
      )
        throw new Error("Invalid upload limit");
      limit = upload_max_bytes + 64 * 1024;
    }
    const declared = Number(request.headers.get("content-length") ?? 0);
    if (declared > limit)
      return Response.json(
        { detail: "Upload exceeds the request limit" },
        { status: 413 },
      );
    let total = 0;
    const body = ["GET", "HEAD"].includes(request.method)
      ? undefined
      : request.body?.pipeThrough(
          new TransformStream<Uint8Array, Uint8Array>({
            transform(chunk, controller) {
              total += chunk.byteLength;
              if (total > limit) {
                tooLarge = true;
                controller.error(new Error("Request too large"));
              } else controller.enqueue(chunk);
            },
          }),
        );
    const response = await fetch(
      `${backend}/api/v1/${path}${new URL(request.url).search}`,
      {
        method: request.method,
        headers,
        body,
        cache: "no-store",
        redirect: "manual",
        signal: AbortSignal.timeout(upload ? 120000 : 15000),
        ...(body ? { duplex: "half" } : {}),
      } as RequestInit & { duplex?: "half" },
    );
    return outgoingResponse(response);
  } catch {
    if (tooLarge)
      return Response.json(
        { detail: "Upload exceeds the request limit" },
        { status: 413 },
      );
    return Response.json(
      { detail: "Backend unavailable. Please try again." },
      { status: 502 },
    );
  }
}
