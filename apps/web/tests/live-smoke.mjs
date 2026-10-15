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

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({
  viewport: { width: 375, height: 900 },
  acceptDownloads: true,
});
fs.mkdirSync("output/playwright/live", { recursive: true });
const scenarios = [
  "sample_news",
  "duplicate_event",
  "no_relevant_news",
  "incomplete_article",
  "conflicting_sources",
  "unavailable_sources",
  "prompt_injection",
];
const results = [];
const errors = [];
page.on("pageerror", (error) => errors.push(error.message));
try {
  for (const scenario of scenarios) {
    await page.goto(webBase + "/create/");
    await page.getByRole("button", { name: "Демо-набор", exact: true }).click();
    await page.getByLabel("Сценарий проверки").selectOption(scenario);
    const demoResponse = page.waitForResponse((response) =>
      response.url().includes(`/api/v1/demo?scenario=${scenario}`),
    );
    await page
      .getByRole("button", { name: "Загрузить демо-набор", exact: true })
      .click();
    assert.equal((await demoResponse).status(), 200);
    await page.getByText(/Загружено материалов:/).waitFor();
    const digestResponse = page.waitForResponse(
      (response) =>
        response.url().endsWith("/api/v1/digest") &&
        response.request().method() === "POST",
    );
    await page.getByRole("button", { name: /Подготовить выпуск/ }).click();
    const response = await digestResponse;
    assert.equal(response.status(), 200);
    const result = await response.json();
    await page.locator(".quality-summary").waitFor();
    assert.equal(
      await page.locator(".quality-warnings li").count(),
      result.warnings.length,
    );
    assert.ok(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    );
    if (scenario === "no_relevant_news" || scenario === "incomplete_article")
      assert.equal(result.event_count, 0);
    if (scenario === "duplicate_event" || scenario === "unavailable_sources")
      assert.equal(result.event_count, 1);
    if (scenario === "conflicting_sources")
      assert.ok(result.events.some((event) => event.conflicts.length > 0));
    fs.writeFileSync(
      `output/playwright/live/${scenario}.json`,
      JSON.stringify(result, null, 2),
    );
    await page.screenshot({
      path: `output/playwright/live/${scenario}-375.png`,
      fullPage: true,
    });
    results.push({
      scenario,
      digest_id: result.digest_id,
      events: result.event_count,
      warnings: result.warnings.length,
    });
    if (scenario === "sample_news") {
      for (const label of ["Markdown ↓", "JSON ↓", "CSV ↓", "HTML письма ↓"]) {
        const downloadEvent = page.waitForEvent("download");
        await page.getByRole("button", { name: label, exact: true }).click();
        const download = await downloadEvent;
        await download.saveAs(
          `output/playwright/live/${download.suggestedFilename()}`,
        );
        assert.ok(
          fs.statSync(`output/playwright/live/${download.suggestedFilename()}`)
            .size > 0,
        );
      }
      await page.getByRole("tab", { name: "Текст поста", exact: true }).click();
      const postDownloadEvent = page.waitForEvent("download");
      await page
        .getByRole("button", { name: "Скачать пост ↓", exact: true })
        .click();
      await (await postDownloadEvent).saveAs("output/playwright/live/post.md");
      await page
        .getByRole("tab", { name: "Предпросмотр письма", exact: true })
        .click();
      assert.equal(await page.locator("iframe").getAttribute("sandbox"), "");
      for (const label of [
        "Источники",
        "Обоснование выбора",
        "Журнал обработки",
        "Проверки",
        "Метрики запуска",
      ]) {
        await page.getByRole("tab", { name: label }).click();
        assert.ok(
          await page.evaluate(
            () => document.documentElement.scrollWidth <= innerWidth,
          ),
          `Tab ${label} overflows`,
        );
      }
    }
  }
  await page.goto(webBase + "/create/");
  await page.getByRole("button", { name: "RSS / HTML", exact: true }).click();
  await page
    .getByLabel("Адреса RSS или HTML, по одному на строку")
    .fill("http://127.0.0.1/private");
  await page
    .getByRole("button", { name: "Получить предпросмотр", exact: true })
    .click();
  await page
    .getByRole("heading", { name: "Журнал получения источников" })
    .waitFor();
  const reset = page.getByRole("button", {
    name: "Сбросить фильтры",
    exact: true,
  });
  assert.equal(await reset.getAttribute("type"), "button");
  await reset.click();
  const sourceFailureResponse = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/v1/digest") &&
      response.request().method() === "POST",
  );
  await page.getByRole("button", { name: /Подготовить выпуск/ }).click();
  const sourceFailure = await (await sourceFailureResponse).json();
  assert.ok(
    sourceFailure.journal.some((row) => row.status === "source_unavailable"),
  );
  await page.goto(webBase + "/result/?id=does-not-exist");
  await page
    .getByRole("button", { name: "Повторить загрузку", exact: true })
    .waitFor();
  await page
    .getByRole("button", { name: "Повторить загрузку", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Повторить загрузку", exact: true })
    .waitFor();
  assert.deepEqual(errors, []);
  fs.writeFileSync(
    "output/playwright/live/results.json",
    JSON.stringify(results, null, 2),
  );
  console.log(
    `PASS: ${results.length} live demo flows at 375px, 5 exports, all result tabs, source-error preservation, missing-result retry; no page errors.`,
  );
} finally {
  await browser.close();
}
