/** Isolated synthetic-fixture visual verification. Never connects to your backend or OpenAI.
 * npm install --prefix .production-smoke/ui-tools --no-save --package-lock=false playwright @axe-core/playwright
 * npm --prefix frontend run build
 * node frontend/scripts/visual-check.mjs
 */
import assert from "node:assert/strict";
import { createServer } from "node:http";
import { createRequire } from "node:module";
import { spawn } from "node:child_process";
import { mkdir, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { fixture, otherOrg } from "./visual-fixtures.mjs";

const frontend = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "..",
);
const root = path.dirname(frontend);
const require = createRequire(
  path.join(root, ".production-smoke/ui-tools/package.json"),
);
const { chromium } = require("playwright");
const AxeBuilder = require("@axe-core/playwright").default;
const output = path.join(
  root,
  process.env.VISUAL_THEME === "dark"
    ? ".production-smoke/phase9-dark"
    : ".production-smoke/phase9-visual",
);
await mkdir(output, { recursive: true });
const backend = createServer(async (req, res) => {
  for await (const chunk of req) {
    void chunk;
  }
  res.setHeader("content-type", "application/json");
  res.setHeader("cache-control", "no-store");
  res.end(JSON.stringify(fixture(req.url, req.method)));
});
await new Promise((resolve, reject) => {
  backend.once("error", reject);
  backend.listen(8002, "127.0.0.1", resolve);
});
const preview = spawn(
  process.execPath,
  ["node_modules/next/dist/bin/next", "start", "-p", "3002", "-H", "127.0.0.1"],
  {
    cwd: frontend,
    windowsHide: true,
    env: {
      ...process.env,
      BACKEND_URL: "http://127.0.0.1:8002",
      LLM_REAL_REQUESTS_ENABLED: "false",
    },
    stdio: "ignore",
  },
);
let browser;
const results = [],
  errors = [];
try {
  for (let i = 0; i < 100; i++) {
    if (preview.exitCode !== null)
      throw new Error("Owned preview process failed; ensure port 3002 is free");
    try {
      if ((await fetch("http://127.0.0.1:3002")).ok) break;
    } catch {
      /* Starting */
    }
    await new Promise((resolve) => setTimeout(resolve, 300));
  }
  browser = await chromium.launch({
    channel:
      process.env.DOCUMIND_BROWSER_CHANNEL ||
      (process.platform === "win32" ? "msedge" : undefined),
    headless: true,
    args: ["--disable-background-networking"],
  });
  for (const size of [
    { name: "desktop", width: 1440, height: 1000 },
    { name: "tablet", width: 1024, height: 900 },
    { name: "mobile", width: 390, height: 844 },
  ].filter(
    (size) => !process.env.VISUAL_SIZE || size.name === process.env.VISUAL_SIZE,
  )) {
    const context = await browser.newContext({
      viewport: { width: size.width, height: size.height },
      reducedMotion: "reduce",
    });
    await context.addInitScript(
      (theme) => {
        if (!localStorage.getItem("documind.theme"))
          localStorage.setItem("documind.theme", theme);
      },
      process.env.VISUAL_THEME === "dark" ? "dark" : "light",
    );
    const page = await context.newPage();
    page.on("pageerror", (error) =>
      errors.push({ size: size.name, error: error.message }),
    );
    await page.route("**/*", (route) => {
      const hostname = new URL(route.request().url()).hostname;
      return ["127.0.0.1", "localhost"].includes(hostname)
        ? route.continue()
        : route.abort();
    });
    for (const screenName of [
      "home",
      "login",
      "signup",
      "dashboard",
      "documents",
      "assistant",
      "intelligence",
      "operations",
    ].filter(
      (name) =>
        !process.env.VISUAL_SCREEN || name === process.env.VISUAL_SCREEN,
    )) {
      await page.goto(
        `http://127.0.0.1:3002/${screenName === "home" ? "" : screenName}${screenName === "operations" ? "?engine=all" : ""}`,
        { waitUntil: "networkidle" },
      );
      if (screenName === "assistant") {
        const sidebar = await page.locator(".assistant-sidebar").boundingBox();
        const chat = await page.locator(".assistant-chat").boundingBox();
        const panel = await page
          .locator(".assistant-conversations")
          .boundingBox();
        assert(
          panel.x + panel.width <= sidebar.x + sidebar.width + 1,
          "Long conversation titles overflow the sidebar",
        );
        if (size.width > 600)
          assert(
            sidebar.x + sidebar.width < chat.x,
            "Assistant columns overlap",
          );
        if (size.width > 800) {
          const navigation = await page.locator(".app-sidebar").boundingBox();
          assert(
            navigation && navigation.x >= 0 && navigation.width > 0,
            "Desktop navigation is missing",
          );
          assert(
            sidebar.x >= navigation.x + navigation.width,
            "Workspace overlaps desktop navigation",
          );
        }
        await page
          .getByRole("button", {
            name: "Commercial terms & obligations",
            exact: true,
          })
          .click();
        await page.getByText(/The agreement sets an annual/).waitFor();
      }
      if (screenName === "intelligence") {
        await page.getByRole("button", { name: /Extraction ·/ }).click();
        await page.getByRole("heading", { name: "contract value" }).waitFor();
      }
      const overflow = await page.evaluate(() => ({
        body: document.documentElement.scrollWidth,
        viewport: innerWidth,
      }));
      assert(
        overflow.body <= overflow.viewport + 1,
        `${size.name}/${screenName}: horizontal page overflow ${JSON.stringify(overflow)}`,
      );
      await page.screenshot({
        path: path.join(output, `${size.name}-${screenName}.png`),
        fullPage: true,
      });
      const scan = await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
        .analyze();
      results.push({
        size: size.name,
        screenName,
        overflow: false,
        violations: scan.violations.map((v) => ({
          id: v.id,
          impact: v.impact,
          nodes: v.nodes.map((n) => ({
            target: n.target,
            summary: n.failureSummary,
          })),
        })),
      });
      if (screenName === "assistant") {
        const citation = page
          .getByRole("button", { name: "Inspect source 1" })
          .first();
        await citation.click();
        const dialog = page.getByRole("dialog", { name: "Source evidence" });
        await dialog.waitFor();
        await page.screenshot({
          path: path.join(output, `${size.name}-evidence.png`),
          fullPage: true,
        });
        await page.keyboard.press("Tab");
        assert(
          await dialog.evaluate((node) =>
            node.contains(document.activeElement),
          ),
          "Dialog focus escaped",
        );
        await page.keyboard.press("Escape");
        await dialog.waitFor({ state: "detached" });
        assert(
          await citation.evaluate((node) => node === document.activeElement),
          "Citation focus not restored",
        );
        if (size.name === "mobile") {
          await page.getByRole("button", { name: "Open navigation" }).click();
          await page
            .getByRole("dialog", { name: "Workspace navigation" })
            .waitFor();
          await page.keyboard.press("Escape");
        }
      }
      if (screenName === "intelligence") {
        await page.getByRole("button", { name: /^Risks \(/ }).click();
        await page.screenshot({
          path: path.join(output, `${size.name}-risks.png`),
          fullPage: true,
        });
        await page.getByRole("button", { name: /Comparison ·/ }).click();
        await page.getByText("GPT interpretation · review required").waitFor();
        await page.screenshot({
          path: path.join(output, `${size.name}-comparison.png`),
          fullPage: true,
        });
      }
    }
    if (
      !process.env.VISUAL_SCREEN ||
      process.env.VISUAL_SCREEN === "assistant"
    ) {
      // Exercise empty and failed GET states without submitting an AI request.
      await page.goto(
        `http://127.0.0.1:3002/assistant?organization=${otherOrg}`,
        { waitUntil: "networkidle" },
      );
      assert.equal(
        await page
          .getByRole("button", {
            name: "Commercial terms & obligations",
            exact: true,
          })
          .count(),
        0,
      );
      for (const state of ["empty", "error"]) {
        if (state === "error") {
          await page.route(
            "**/api/backend/organizations/*/intelligence/status",
            (route) =>
              route.fulfill({
                status: 503,
                contentType: "application/json",
                body: JSON.stringify({
                  detail: "Service temporarily unavailable. Please try again.",
                }),
              }),
          );
          await page.reload({ waitUntil: "networkidle" });
          await page
            .getByRole("alert")
            .filter({ hasText: "Service temporarily unavailable" })
            .waitFor();
        }
        await page.screenshot({
          path: path.join(output, `${size.name}-assistant-${state}.png`),
          fullPage: true,
        });
        const scan = await new AxeBuilder({ page })
          .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
          .analyze();
        results.push({
          size: size.name,
          screenName: `assistant-${state}`,
          violations: scan.violations.map(({ id, impact }) => ({ id, impact })),
        });
      }
      if (size.name === "mobile") {
        await page.getByRole("button", { name: "Open navigation" }).click();
        await page
          .getByRole("button", { name: "Your account", exact: true })
          .click();
      } else {
        await page.getByRole("button", { name: "Open account menu" }).click();
      }
      await page
        .getByRole("dialog", { name: "Your account", exact: true })
        .waitFor();
      await page.screenshot({
        path: path.join(output, `${size.name}-account.png`),
        fullPage: true,
      });
      await page.keyboard.press("Escape");
    }
    for (const theme of ["dark", "light"]) {
      await page.getByLabel("Color theme").selectOption(theme);
      assert.equal(
        await page.locator("html").getAttribute("data-theme"),
        theme,
      );
      await page.reload({ waitUntil: "networkidle" });
      assert.equal(
        await page.locator("html").getAttribute("data-theme"),
        theme,
        "Theme did not survive reload",
      );
      assert.equal(await page.getByLabel("Color theme").inputValue(), theme);
    }
    await context.close();
  }
} finally {
  await browser?.close();
  preview.kill();
  backend.closeAllConnections();
  backend.close();
  await writeFile(
    path.join(output, "report.json"),
    JSON.stringify({ results, errors }, null, 2),
  );
}
assert.equal(errors.length, 0, "Browser runtime errors; inspect report.json");
const violations = results.reduce(
  (sum, result) => sum + result.violations.length,
  0,
);
console.log(
  `Visual checks completed: ${results.length} screens; ${violations} accessibility findings. Screenshots/report: ${path.relative(root, output)}`,
);
if (violations) process.exitCode = 1;
