import type { DigestResult } from "../lib/types";
import { summarizeQuality, textLength } from "../lib/quality";

export function QualitySummary({ result }: { result: DigestResult }) {
  const quality = summarizeQuality(result);
  const requiresReview =
    quality.failedChecks.length > 0 ||
    quality.conflictingEvents > 0 ||
    quality.preliminaryEvents > 0 ||
    quality.warningCount > 0;
  return (
    <section className="panel quality-summary" aria-labelledby="quality-title">
      <div className="quality-heading">
        <div>
          <div className="eyebrow">ПЕРЕД ПУБЛИКАЦИЕЙ</div>
          <h2 id="quality-title">Качество выпуска</h2>
        </div>
        <span
          className={`badge ${requiresReview ? "warning" : quality.checksTotal ? "good" : ""}`}
        >
          {requiresReview
            ? "Есть оговорки — проверьте"
            : quality.checksTotal
              ? "Проверки пройдены"
              : "Проверки не получены"}
        </span>
      </div>
      <dl className="quality-facts">
        <div>
          <dt>Проверки API</dt>
          <dd>
            {quality.checksTotal
              ? `${quality.checksPassed} из ${quality.checksTotal}`
              : "Нет данных"}
          </dd>
        </div>
        <div>
          <dt>Предварительные события</dt>
          <dd>{quality.preliminaryEvents}</dd>
        </div>
        <div>
          <dt>События с противоречиями</dt>
          <dd>{quality.conflictingEvents}</dd>
        </div>
        <div>
          <dt>Предупреждения</dt>
          <dd>{quality.warningCount}</dd>
        </div>
      </dl>
      <p className="field-hint">
        Проверки отражают обработку и соответствие формату. Достоверность
        публикаций требует редакционной оценки. Модель:{" "}
        {result.model_name || "не указана"}; режим:{" "}
        {typeof result.metrics.mode === "string"
          ? result.metrics.mode
          : "нет данных"}
        .
      </p>
      {quality.failedChecks.length > 0 && (
        <p className="failed-checks">
          <strong>Не пройдены:</strong> {quality.failedChecks.join("; ")}.
          Подробности — во вкладке «Проверки».
        </p>
      )}
      {result.warnings.length > 0 && (
        <div className="quality-warnings">
          <strong>Все предупреждения выпуска</strong>
          <ul>
            {result.warnings.map((warning, index) => (
              <li key={index}>{warning}</li>
            ))}
          </ul>
        </div>
      )}
      <div className="length-grid">
        <TextCounter text={result.digest_text} limit={4000} label="Дайджест" />
        <TextCounter text={result.post_text} limit={2000} label="Пост" />
      </div>
    </section>
  );
}

export function TextCounter({
  text,
  limit,
  label,
}: {
  text: string;
  limit: number;
  label: string;
}) {
  const length = textLength(text);
  return (
    <div
      className={`text-counter ${length.withoutUrls > limit ? "over-limit" : ""}`}
    >
      <span>{label}</span>
      <strong>
        {length.withoutUrls.toLocaleString("ru-RU")} /{" "}
        {limit.toLocaleString("ru-RU")}
      </strong>
      <small>
        знаков без URL · всего {length.total.toLocaleString("ru-RU")}
        {length.withoutUrls > limit ? " · Лимит превышен" : ""}
      </small>
    </div>
  );
}
