import test from "node:test";
import assert from "node:assert/strict";
import { demoScenarios, loadDemoScenario } from "../src/lib/demo.ts";

test("all required demo scenarios request the explicit scenario query", async () => {
  assert.deepEqual(
    demoScenarios.map((s) => s.id),
    [
      "sample_news",
      "duplicate_event",
      "no_relevant_news",
      "incomplete_article",
      "conflicting_sources",
      "unavailable_sources",
      "prompt_injection",
    ],
  );
  for (const scenario of demoScenarios) {
    let observed = "";
    const result = await loadDemoScenario(scenario.id, async (input) => {
      observed = String(input);
      return Response.json({
        articles: [],
        control_time: "2026-10-14T12:00:00+03:00",
        scenario: scenario.id,
        description: "Описание",
      });
    });
    assert.ok(observed.endsWith(`/api/v1/demo?scenario=${scenario.id}`));
    assert.equal(result.scenario, scenario.id);
    assert.equal(result.description, "Описание");
  }
});
