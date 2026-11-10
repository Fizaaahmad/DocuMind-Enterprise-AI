import { proxyRequest } from "../../../../lib/proxy";

export const runtime = "nodejs";

async function handler(
  request: Request,
  context: { params: Promise<{ path: string[] }> },
) {
  return proxyRequest(request, (await context.params).path);
}

export { handler as GET, handler as POST, handler as PATCH, handler as DELETE };
