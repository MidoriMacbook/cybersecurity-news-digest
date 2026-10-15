import test from "node:test";
import assert from "node:assert/strict";
import {
  textLength,
  summarizeQuality,
  displayMetric,
} from "../src/lib/quality.ts";

test("length counts Unicode characters and omits URLs from format limits", () => {
  assert.deepEqual(textLength("Факт 🚀 https://example.org/news"), {
    total: 31,
    withoutUrls: 7,
  });
  assert.deepEqual(textLength(""), { total: 0, withoutUrls: 0 });
});

test("quality uses actual checks and preserves every warning and conflict", () => {
  const quality = summarizeQuality({
    checks: [
      { name: "Period", passed: true, details: "ok" },
      { name: "Facts", passed: false, details: "missing" },
    ],
    events: [
      { is_preliminary: true, conflicts: ["Mismatch"] },
      { is_preliminary: false, conflicts: [] },
    ],
    warnings: ["Fallback", "Missing date"],
  });
  assert.deepEqual(quality, {
    checksPassed: 1,
    checksTotal: 2,
    failedChecks: ["Facts"],
    preliminaryEvents: 1,
    conflictingEvents: 1,
    warningCount: 2,
  });
  assert.equal(
    summarizeQuality({ checks: [], events: [], warnings: [] }).checksTotal,
    0,
  );
});

test("unavailable usage and cost never display as a measured zero", () => {
  assert.equal(
    displayMetric("tokens_used", {
      tokens_used: 0,
      token_usage_available: false,
    }),
    "Недоступно",
  );
  assert.equal(
    displayMetric("tokens_used", {
      tokens_used: 0,
      token_usage_available: true,
    }),
    "0",
  );
  assert.equal(displayMetric("cost_usd", { cost_usd: null }), "Недоступно");
  assert.equal(displayMetric("cost_usd", { cost_usd: 0 }), "0");
});
