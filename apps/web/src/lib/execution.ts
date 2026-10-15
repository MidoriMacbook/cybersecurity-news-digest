import type { Health, RewrittenCopy } from "./types.ts";

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

type ServerHealth = Pick<
  Health,
  "mode" | "llm_configured" | "execution_status"
>;

export function serverModeLabel(health: ServerHealth) {
  const configured =
    health.llm_configured === true ||
    (health.llm_configured == null && ["ai", "api"].includes(health.mode));
  if (!configured) return "Обработка без ИИ";
  if (health.execution_status?.last_ai_run?.mode === "fallback")
    return "Готов резервный результат";
  if (
    health.execution_status?.last_ai_run?.mode === "ai" &&
    health.execution_status.last_successful_ai_run?.mode === "ai"
  )
    return "Выпуск с ИИ готов";
  return "ИИ настроен";
}

export function presentationStatus(
  health: (ServerHealth & { status: string }) | null,
  error = "",
) {
  if (!health || health.status !== "ok") {
    const failed = Boolean(error || health);
    return {
      title: failed ? "Нет соединения" : "Проверяем соединение",
      api: failed
        ? health
          ? "Сервис временно недоступен"
          : "Сервис недоступен"
        : "Подключаемся…",
      demo: failed ? "Пример пока недоступен" : "Загружаем пример",
      key: "Проверяем подключение ИИ",
      description: failed
        ? "Обновите страницу, чтобы проверить соединение."
        : "Подключаемся к сервису.",
      hint: "Статус обновится после подключения.",
    };
  }
  const configured =
    health.llm_configured === true ||
    (health.llm_configured == null && ["ai", "api"].includes(health.mode));
  const last = health.execution_status?.last_ai_run;
  const success = health.execution_status?.last_successful_ai_run;
  const completed = success ? new Date(success.completed_at) : null;
  const successHint =
    success && completed && !Number.isNaN(completed.getTime())
      ? `Последний выпуск с ИИ: ${new Intl.DateTimeFormat("ru-RU", {
          dateStyle: "short",
          timeStyle: "short",
          timeZone: "Europe/Moscow",
        }).format(completed)} МСК.`
      : "Готовый выпуск появится в разделе «Результат».";
  return {
    title: configured ? serverModeLabel(health) : "Обработка без ИИ",
    api: "Сервис доступен",
    demo: "Пример доступен",
    key: configured ? "ИИ можно выбрать при создании" : "ИИ не подключён",
    description: configured
      ? last?.mode === "fallback"
        ? "Последний выпуск подготовлен без ИИ."
        : last?.mode === "ai" && success?.mode === "ai"
          ? "ИИ подготовил выпуск. Источники и подробности доступны в результате."
          : "Создайте выпуск, чтобы проверить работу ИИ."
      : "Сервис подготовит выпуск из исходных материалов.",
    hint: configured
      ? last
        ? successHint
        : "При создании включите «Использовать ИИ»."
      : "Пример можно открыть без настройки ИИ.",
  };
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
