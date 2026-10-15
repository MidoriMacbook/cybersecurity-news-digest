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
  if (!configured) return "Mock · ключ не настроен";
  if (health.execution_status?.last_ai_run?.mode === "fallback")
    return "ИИ вызван, показан резервный результат";
  if (
    health.execution_status?.last_ai_run?.mode === "ai" &&
    health.execution_status.last_successful_ai_run?.mode === "ai"
  )
    return "ИИ-прогон подтверждён";
  return "ИИ настроен · прогон не подтверждён";
}

export function presentationStatus(
  health: (ServerHealth & { status: string }) | null,
  error = "",
) {
  if (!health || health.status !== "ok") {
    const failed = Boolean(error || health);
    return {
      title: failed ? "Сервер недоступен" : "Проверяем режим",
      api: failed
        ? health
          ? "API сообщает ошибку"
          : "API недоступен"
        : "Проверяем API…",
      demo: failed
        ? "Демо временно недоступно"
        : "Доступность демо проверяется",
      key: "Статус ключа не подтверждён",
      description: failed
        ? "Не удалось подтвердить готовность сервера. Обновите страницу, чтобы повторить проверку."
        : "Ожидаем ответ сервера. Первый запрос после простоя может занять больше времени.",
      hint: "Режим будет показан после успешного ответа API.",
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
      ? `Последний успешный AI-прогон: ${new Intl.DateTimeFormat("ru-RU", {
          dateStyle: "short",
          timeStyle: "short",
          timeZone: "Europe/Moscow",
        }).format(
          completed,
        )} МСК · ${success.model_name} · ${success.prompt_version}.`
      : "Успешный AI-прогон в текущем хранилище не подтверждён.";
  return {
    title: configured ? serverModeLabel(health) : "Демонстрационный режим",
    api: "API отвечает",
    demo: "Демо-режим доступен",
    key: configured ? "AI-конфигурация добавлена" : "AI-ключ не подключён",
    description: configured
      ? last?.mode === "fallback"
        ? "Последний AI-запуск завершился в режиме fallback. Показан безопасный локальный результат."
        : last?.mode === "ai" && success?.mode === "ai"
          ? "Последний AI-выпуск принят после проверок цитат и семантической сверки. Это не подтверждает истинность исходной новости."
          : "Backend настроен для ИИ. Успех обращения проверяйте в новом результате."
      : "Сейчас используется демонстрационный режим без внешней модели.",
    hint: configured
      ? last
        ? successHint
        : "Демо доступно без обращения к модели. Настройка ключа не подтверждает его работоспособность."
      : "Реальная модель не подключена. AI-режим доступен после настройки backend.",
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
