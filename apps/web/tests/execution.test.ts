import assert from "node:assert/strict";
import test from "node:test";
import {
  executionDetails,
  serverModeLabel,
  eventDigest,
} from "../src/lib/execution.ts";

test("actual fallback is shown even when server is configured for AI", () => {
  const run = executionDetails({
    mode: "fallback",
    llm_attempts: 2,
    token_usage: { input: null, output: null, total: null },
    metrics: { mode: "api", tokens_used: 0 },
  });
  assert.equal(run.mode, "fallback");
  assert.equal(run.label, "Fallback · локальная обработка");
  assert.equal(run.attempts, 2);
  assert.equal(run.tokens, "Недоступно");
});

test("old session results keep honest mode and unknown usage", () => {
  const run = executionDetails({
    metrics: {
      mode: "api",
      model_calls: 1,
      tokens_used: 0,
      token_usage_available: false,
    },
  });
  assert.equal(run.label, "ИИ · прежний редакционный режим");
  assert.equal(run.tokens, "Недоступно");
  assert.equal(run.started, "Нет данных");
});

test("measured zero tokens and absent token usage remain distinct", () => {
  assert.equal(
    executionDetails({
      mode: "mock",
      token_usage: { input: 0, output: 0, total: 0 },
      metrics: {},
    }).tokens,
    "0",
  );
  assert.equal(
    executionDetails({ mode: "ai", metrics: {} }).tokens,
    "Недоступно",
  );
  assert.equal(
    executionDetails({ mode: "ai", metrics: {} }).label,
    "ИИ · проверенный пересказ",
  );
});

test("configured provider is not presented as a successful real AI run", () => {
  assert.equal(
    serverModeLabel({ mode: "ai", llm_configured: true }),
    "ИИ настроен · прогон не подтверждён",
  );
  assert.equal(
    serverModeLabel({ mode: "mock", llm_configured: false }),
    "Mock · ключ не настроен",
  );
});

test("visible digest uses accepted AI copy and never a rejected candidate", () => {
  const event = { event_id: "a", summary: "Исходный фрагмент" };
  const ai_copy = {
    events: [
      {
        event_id: "a",
        digest: [{ text: "Принятый пересказ", evidence: [] }],
        post: [],
      },
    ],
  };
  assert.deepEqual(eventDigest({ mode: "ai", ai_copy }, event), [
    "Принятый пересказ",
  ]);
  assert.deepEqual(eventDigest({ mode: "fallback", ai_copy }, event), [
    "Исходный фрагмент",
  ]);
  assert.deepEqual(
    eventDigest(
      { mode: "ai", ai_copy },
      { event_id: "b", summary: "Другое событие" },
    ),
    ["Другое событие"],
  );
});
