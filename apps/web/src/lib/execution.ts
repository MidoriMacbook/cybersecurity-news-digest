import type { RewrittenCopy } from "./types.ts";

export function eventDigest(
  result: { mode?: string; ai_copy?: RewrittenCopy | null },
  event: { event_id: string; summary: string },
): string[] {
  const rewritten =
    result.mode === "ai"
      ? result.ai_copy?.events.find((item) => item.event_id === event.event_id)
      : null;
  return rewritten?.digest.length
    ? rewritten.digest.map((sentence) => sentence.text)
    : [event.summary];
}

type RunInput = {
  mode?: "ai" | "mock" | "fallback";
  llm_attempts?: number;
  token_usage?: {
    input: number | null;
    output: number | null;
    total: number | null;
  };
  started_at?: string;
  completed_at?: string;
  metrics: Record<string, unknown>;
};

export function serverModeLabel(health: {
  mode: string;
  llm_configured?: boolean;
}) {
  return health.llm_configured === true ||
    (health.llm_configured == null && ["ai", "api"].includes(health.mode))
    ? "ИИ настроен · прогон не подтверждён"
    : "Mock · ключ не настроен";
}

export function executionDetails(result: RunInput) {
  const mode =
    result.mode ||
    (result.metrics.mode === "api"
      ? "legacy_ai"
      : result.metrics.mode === "mock"
        ? "mock"
        : "unknown");
  const labels: Record<string, string> = {
    ai: "ИИ · проверенный пересказ",
    mock: "Mock · без обращения к модели",
    fallback: "Fallback · локальная обработка",
    legacy_ai: "ИИ · прежний редакционный режим",
    unknown: "Режим не указан",
  };
  const attempts = result.llm_attempts ?? result.metrics.model_calls;
  const total = result.token_usage
    ? result.token_usage.total
    : result.metrics.token_usage_available === true
      ? result.metrics.tokens_used
      : null;
  return {
    mode,
    label: labels[mode],
    attempts:
      typeof attempts === "number" &&
      Number.isInteger(attempts) &&
      attempts >= 0
        ? attempts
        : null,
    tokens:
      typeof total === "number" && Number.isInteger(total) && total >= 0
        ? String(total)
        : "Недоступно",
    started: result.started_at || "Нет данных",
    completed: result.completed_at || "Нет данных",
  };
}
