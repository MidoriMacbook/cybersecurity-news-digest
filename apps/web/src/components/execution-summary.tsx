import type { DigestResult } from "../lib/types";
import { executionDetails } from "../lib/execution";
import { formatDate } from "../lib/input";

export function ExecutionSummary({ result }: { result: DigestResult }) {
  const run = executionDetails(result);
  return (
    <section
      className="panel execution-summary"
      aria-label="Режим и происхождение выпуска"
    >
      <div className="execution-title">
        <strong>{run.label}</strong>
        <span className="badge">
          {result.application_version || "Версия не указана"}
        </span>
      </div>
      <p className="field-hint">
        {run.mode === "mock"
          ? "Реальная модель не использовалась. Выпуск собран локальными правилами."
          : run.mode === "fallback"
            ? "ИИ не дал принятого результата. Сохранён безопасный экстрактивный выпуск; причины указаны в предупреждениях."
            : run.mode === "ai"
              ? "Пересказ прошёл проверки цитат и семантическую сверку. Эти проверки не подтверждают истинность исходной новости."
              : "Выпуск сохранён в прежнем формате; подробности обработки доступны в метриках."}
      </p>
      <dl className="execution-facts">
        <div>
          <dt>Модель</dt>
          <dd>{result.model_name || "Не указана"}</dd>
        </div>
        <div>
          <dt>Промпт</dt>
          <dd>{result.prompt_version || "Не указан"}</dd>
        </div>
        <div>
          <dt>Обращений к модели</dt>
          <dd>{run.attempts ?? "Нет данных"}</dd>
        </div>
        <div>
          <dt>Всего токенов</dt>
          <dd>{run.tokens}</dd>
        </div>
        <div>
          <dt>Начало запуска · Москва</dt>
          <dd>
            {result.started_at ? formatDate(result.started_at) : "Нет данных"}
          </dd>
        </div>
        <div>
          <dt>Завершение · Москва</dt>
          <dd>
            {result.completed_at
              ? formatDate(result.completed_at)
              : "Нет данных"}
          </dd>
        </div>
      </dl>
    </section>
  );
}
