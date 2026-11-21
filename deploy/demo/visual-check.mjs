// Optional local browser verification using the existing operator Playwright install.
// No new application dependency. Only localhost traffic is permitted.
import { createRequire } from "node:module";
import { mkdir, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";

const require = createRequire(new URL("../../.production-smoke/ui-tools/package.json", import.meta.url));
const { chromium } = require("playwright");
const output = new URL("./verification/", import.meta.url);
await mkdir(output, { recursive: true });
const browser = await chromium.launch({ channel: "msedge", headless: true });
const errors = [], checks = [];
try {
  // Local self-signed certificate only. HTTP smoke uses explicit CA verification.
  const context = await browser.newContext({ ignoreHTTPSErrors: true, reducedMotion: "reduce" });
  const page = await context.newPage();
  page.on("pageerror", error => errors.push(error.message));
  await page.route("**/*", route => {
    const url = new URL(route.request().url());
    return url.hostname === "localhost" ? route.continue() : route.abort();
  });
  await page.goto("https://localhost:8448/login", { waitUntil: "networkidle" });
  await page.getByRole("button", { name: "Explore the demo" }).click();
  await page.waitForURL("**/dashboard");
  for (const width of [1440, 768, 390]) {
    await page.setViewportSize({ width, height: 1000 });
    for (const route of ["dashboard", "documents", "assistant", "intelligence", "operations"]) {
      await page.goto(`https://localhost:8448/${route}`, { waitUntil: "networkidle" });
      await page.getByText("Northstar Research · Fictional Demo", { exact: true }).first().waitFor({ state: "attached" });
      if (route === "assistant") {
        await page.getByText("Service agreement · saved mock preview", { exact: true }).first().waitFor();
        await page.locator(".chat-transcript").getByText("What are the service agreement terms?", { exact: true }).waitFor();
        if (!(await page.getByRole("button", { name: "Ask assistant", exact: true }).isDisabled())) throw Error("Composer enabled");
      }
      if (route === "intelligence" && !(await page.getByRole("button", { name: "Analysis unavailable in demo" }).isDisabled())) throw Error("Analysis enabled");
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1);
      if (overflow) throw Error(`Horizontal overflow: ${route} at ${width}`);
      await page.screenshot({ path: fileURLToPath(new URL(`${route}-${width}.png`, output)), fullPage: false });
      checks.push({ route, width, overflow });
    }
  }
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("https://localhost:8448/assistant", { waitUntil: "networkidle" });
  await page.getByLabel("Color theme").selectOption("dark");
  await page.locator(".source-chip").first().click();
  await page.getByRole("dialog", { name: "Source evidence" }).waitFor();
  await page.screenshot({ path: fileURLToPath(new URL("assistant-evidence-dark.png", output)), fullPage: false });
  checks.push({ route: "assistant-evidence", width: 1440, theme: "dark" });
  if (errors.length) throw Error(errors.join("; "));
  await writeFile(new URL("browser-checks.json", output), JSON.stringify({ checks, errors, localOnly: true }, null, 2));
  process.stdout.write(`Browser verification passed: ${checks.length} page/viewport combinations.\n`);
} finally {
  await browser.close();
}
