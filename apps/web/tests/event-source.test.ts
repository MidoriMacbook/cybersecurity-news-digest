import test from "node:test";
import assert from "node:assert/strict";
import { selectEventSource } from "../src/lib/event-source.ts";
import type { Article } from "../src/lib/types.ts";

const article = (url: string, published_at: string): Article => ({
  id: "a",
  title: "Publication",
  source: "Source",
  source_type: "official",
  text: "Facts",
  url,
  published_at,
});
const excluded = article(
  "https://example.org/old",
  "2026-10-13T16:00:00+03:00",
);
const accepted = article(
  "https://example.org/current",
  "2026-10-14T12:00:00+03:00",
);
const event = {
  event_id: "event-1",
  evidence: [{ source_id: "a", fragment: "Facts", url: accepted.url }],
};

test("duplicate IDs use the journal-linked publication instead of an outside-period first match", () => {
  const result = {
    sources: [excluded, accepted],
    journal: [
      { id: "a", event_id: null },
      { id: "a", event_id: "event-1" },
    ],
  };
  assert.equal(selectEventSource(result, event, "a"), accepted);
  assert.equal(
    selectEventSource(result, event, "a")?.published_at,
    "2026-10-14T12:00:00+03:00",
  );
});

test("an unreadable duplicate cannot replace the normal source or quote link", () => {
  const unreadable = { ...excluded, text: null, read_error: "Timeout" };
  const result = {
    sources: [unreadable, accepted],
    journal: [
      { id: "a", event_id: null },
      { id: "a", event_id: "event-1" },
    ],
  };
  assert.equal(selectEventSource(result, event, "a"), accepted);
  assert.equal(selectEventSource(result, event, "a", accepted.url), accepted);
});

test("shared IDs across events are resolved by event membership", () => {
  const result = {
    sources: [excluded, accepted],
    journal: [
      { id: "a", event_id: "other-event" },
      { id: "a", event_id: "event-1" },
    ],
  };
  assert.equal(selectEventSource(result, event, "a"), accepted);
});

test("evidence URL disambiguates matching IDs within an event; unknown URL never picks another quote source", () => {
  const result = {
    sources: [excluded, accepted],
    journal: [
      { id: "a", event_id: "event-1" },
      { id: "a", event_id: "event-1" },
    ],
  };
  assert.equal(selectEventSource(result, event, "a"), accepted);
  assert.equal(selectEventSource(result, event, "a", excluded.url), excluded);
  assert.equal(
    selectEventSource(result, event, "a", "https://example.org/unknown"),
    undefined,
  );
});

test("missing journal membership fails closed rather than borrowing an excluded source", () => {
  const result = {
    sources: [excluded, accepted],
    journal: [{ id: "a", event_id: null }],
  };
  assert.equal(selectEventSource(result, event, "a"), undefined);
  assert.equal(selectEventSource(result, event, "unknown"), undefined);
});
