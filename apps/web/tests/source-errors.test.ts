import test from "node:test";
import assert from "node:assert/strict";
import { preserveSourceErrors } from "../src/lib/source-errors.ts";

test("preview failures remain articles with original provenance and explicit read errors", () => {
  const available = {
    id: "good",
    title: "Good",
    text: "Content",
    source: "Source",
    source_type: "official",
    url: "https://example.org/good",
    published_at: "2026-10-14T12:00:00+03:00",
  };
  const result = preserveSourceErrors(
    [available],
    [
      {
        id: null,
        title: "Unavailable",
        source: "Feed",
        source_type: "official",
        url: "https://example.org/bad",
        published_at: null,
        errors: ["Timeout", "Read failed"],
        exclusion_reason: "Unavailable",
      },
      { ...available, errors: [], exclusion_reason: null },
      {
        id: "parse",
        title: null,
        source: null,
        source_type: null,
        url: "https://example.org/parse",
        published_at: null,
        errors: [],
        exclusion_reason: "Ошибка разбора",
      },
    ],
  );
  assert.equal(result.length, 3);
  assert.deepEqual(result[0], available);
  assert.equal(result[1].id, "source-error-0");
  assert.equal(result[1].read_error, "Timeout; Read failed");
  assert.equal(result[1].text, null);
  assert.equal(result[1].url, "https://example.org/bad");
  assert.equal(result[2].read_error, "Ошибка разбора");
});
