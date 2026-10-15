// Run with Node after installing Playwright and its Chromium browser.
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

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  const results = [];
  fs.mkdirSync("output/playwright", { recursive: true });
  try {
    for (const width of [375, 768, 1024, 1440]) {
      await page.setViewportSize({ width, height: 900 });
      for (const path of ["/", "/create/", "/result/", "/journal/", "/docs/"]) {
        await page.goto(`${webBase}${path}`);
        await page.locator("h1").waitFor();
        const layout = await page.evaluate(() => ({
          viewport: innerWidth,
          width: document.documentElement.scrollWidth,
          bodyFont: getComputedStyle(document.body).fontSize,
        }));
        assert.ok(
          layout.width <= width,
          `${path} overflows at ${width}: ${layout.width}`,
        );
        assert.equal(layout.bodyFont, "16px");
        results.push({ path, width, ...layout });
      }
      await page.goto(webBase + "/create/");
      await page
        .getByRole("button", { name: "Демо-набор", exact: true })
        .click();
      assert.equal(
        await page.getByLabel("Сценарий проверки").locator("option").count(),
        7,
      );
      await page.screenshot({
        path: `output/playwright/create-${width}.png`,
        fullPage: true,
      });
    }
    fs.writeFileSync(
      "output/playwright/responsive-results.json",
      JSON.stringify(results, null, 2),
    );
    console.log(
      `PASS: ${results.length} route/viewport checks; 7 demo scenarios visible; screenshots saved.`,
    );
  } finally {
    await browser.close();
  }
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
