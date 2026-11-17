// No secrets or public backend origins are embedded at build time.
const value = process.env.BACKEND_URL;
try {
  const url = new URL(value);
  if (!value || !["http:", "https:"].includes(url.protocol) || url.username || url.password || url.pathname !== "/" || url.search || url.hash)
    throw new Error();
} catch {
  process.stderr.write("Production requires a valid server-only BACKEND_URL\n");
  process.exit(1);
}
import("./server.js").catch(() => {
  process.stderr.write("Production frontend failed to start\n");
  process.exit(1);
});
