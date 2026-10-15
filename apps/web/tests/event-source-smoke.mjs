import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
const webBase = process.env.WEB_BASE_URL || "http://127.0.0.1:3000";
const runtimeRoot = process.env.BROWSER_RUNTIME_PATH;
const { chromium } = runtimeRoot
  ? await import(
      pathToFileURL(path.join(runtimeRoot, "playwright/index.mjs")).href
    )
  : await import("playwright");

// Run live-smoke first to capture the API fixture.
const captured = JSON.parse(
  fs.readFileSync("output/playwright/live/unavailable_sources.json", "utf8"),
);
const browser = await chromium.launch({ headless: true });
try {
  for (const scenario of ["outside_period", "read_error"]) {
    const result = structuredClone(captured);
    const accepted = result.sources[1];
    const excluded = result.sources[0];
    excluded.id = accepted.id;
    excluded.url = "https://example.org/excluded-duplicate";
    excluded.published_at = "2026-10-13T16:00:00+03:00";
    result.journal[0].id = accepted.id;
    result.journal[0].event_id = null;
    if (scenario === "outside_period") {
      excluded.text = "Excluded old publication";
      excluded.read_error = null;
      result.journal[0].status = "excluded_outside_period";
    }
    // Test the quote fallback without a direct evidence URL as well.
    result.events[0].evidence[0].url = null;
    const context = await browser.newContext({
      viewport: { width: 375, height: 900 },
    });
    await context.addInitScript(
      (fixture) =>
        sessionStorage.setItem("cyberdigest.result", JSON.stringify(fixture)),
      result,
    );
    const page = await context.newPage();
    await page.goto(webBase + "/result/");
    const source = page.locator(".event-sources a");
    await source.waitFor();
    assert.equal(await source.getAttribute("href"), accepted.url);
    assert.match(await source.innerText(), /14 окт\. 2026/);
    assert.ok(!(await source.innerText()).includes(excluded.url));
    await page
      .getByText("Факты и подтверждающие фрагменты", { exact: true })
      .click();
    assert.equal(
      await page.locator("blockquote a").first().getAttribute("href"),
      accepted.url,
    );
    await page.getByRole("tab", { name: "Источники" }).click();
    assert.equal(await page.locator(".source-card").count(), 2);
    await context.close();
  }
  console.log(
    "PASS: duplicate-ID source URL/date and quote fallback use the journal-linked publication after session hydration; both input sources remain visible.",
  );
} finally {
  await browser.close();
}
