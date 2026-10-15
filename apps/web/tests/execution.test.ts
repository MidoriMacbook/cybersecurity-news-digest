import assert from "node:assert/strict";
import test from "node:test";
import {
  executionDetails,
  serverModeLabel,
  eventDigest,
  presentationStatus,
} from "../src/lib/execution.ts";

test("presentation never invents API or demo availability before health succeeds", () => {
  assert.equal(presentationStatus(null).api, "Проверяем API…");
  assert.equal(presentationStatus(null).demo, "Доступность демо проверяется");
  assert.equal(presentationStatus(null, "network error").api, "API недоступен");
  assert.equal(
    presentationStatus(null, "network error").demo,
    "Демо временно недоступно",
  );
  assert.equal(
    presentationStatus({ status: "error", mode: "mock" }).api,
    "API сообщает ошибку",
  );
});

test("keyless presentation explicitly distinguishes demo from real AI", () => {
  const status = presentationStatus({
    status: "ok",
    mode: "mock",
    llm_configured: false,
  });
  assert.equal(status.api, "API отвечает");
  assert.equal(status.demo, "Демо-режим доступен");
  assert.equal(status.title, "Демонстрационный режим");
  assert.equal(
    status.description,
    "Сейчас используется демонстрационный режим без внешней модели.",
  );
  assert.equal(
    status.hint,
    "Реальная модель не подключена. AI-режим доступен после настройки backend.",
  );
});

test("configured presentation never treats key presence as successful AI execution", () => {
  const status = presentationStatus({
    status: "ok",
    mode: "ai",
    llm_configured: true,
  });
  assert.equal(status.title, "ИИ настроен · прогон не подтверждён");
  assert.match(status.description, /новом результате/);
  assert.equal(status.api, "API отвечает");
  assert.equal(
    presentationStatus({ status: "ok", mode: "ai", llm_configured: false })
      .title,
    "Демонстрационный режим",
  );
});

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

test("public persisted success confirms AI and names its completion", () => {
  const run = {
    digest_id: "success",
    mode: "ai" as const,
    model_name: "fixture-model",
    prompt_version: "editorial-v3",
    completed_at: "2026-10-15T14:00:00+00:00",
    application_version: "1.6.2",
  };
  const health = {
    status: "ok",
    mode: "ai",
    llm_configured: true,
    execution_status: { last_ai_run: run, last_successful_ai_run: run },
  };
  assert.equal(serverModeLabel(health), "ИИ-прогон подтверждён");
  assert.match(presentationStatus(health).hint, /fixture-model/);
  assert.match(presentationStatus(health).hint, /editorial-v3/);
  assert.match(presentationStatus(health).hint, /17:00/);
});

test("latest fallback is visible while prior successful evidence remains", () => {
  const success = {
    digest_id: "success",
    mode: "ai" as const,
    model_name: "fixture-model",
    prompt_version: "editorial-v3",
    completed_at: "2026-10-15T14:00:00+00:00",
    application_version: "1.6.2",
  };
  const health = {
    status: "ok",
    mode: "ai",
    llm_configured: true,
    execution_status: {
      last_ai_run: { ...success, mode: "fallback" as const },
      last_successful_ai_run: success,
    },
  };
  assert.equal(
    serverModeLabel(health),
    "ИИ вызван, показан резервный результат",
  );
  assert.match(presentationStatus(health).hint, /Последний успешный/);
  assert.match(presentationStatus(health).description, /fallback/);
});
