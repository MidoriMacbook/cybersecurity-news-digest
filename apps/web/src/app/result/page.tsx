"use client";
import Link from "next/link";
import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { selectResultView } from "../../lib/result-view";
import type { RequestedResult } from "../../lib/result-view";
import { request } from "../../lib/api";
import type { DigestResult } from "../../lib/types";
import {
  Alert,
  EmptyResult,
  MetricGrid,
  PageHeading,
  useWorkspace,
} from "../../components/workspace";
import { Journal, SourceLink, sourceLabels } from "../../components/journal";
import { download, formatDate, journalCsv } from "../../lib/input";
import { QualitySummary } from "../../components/quality-summary";
import { displayMetric } from "../../lib/quality";
import { selectEventSource } from "../../lib/event-source";
const tabs = [
  "Дайджест",
  "Предпросмотр письма",
  "Текст поста",
  "Источники",
  "Обоснование выбора",
  "Журнал обработки",
  "Проверки",
  "Метрики запуска",
];
const factorNames: Record<string, string> = {
  impact: "Воздействие",
  scale: "Масштаб",
  urgency: "Срочность",
  audience_relevance: "Значимость для аудитории",
  source_quality: "Качество источников",
  recency: "Актуальность",
  confirmation: "Независимое подтверждение",
  new_facts: "Новые факты",
  completeness: "Полнота данных",
};
const metricNames: Record<string, string> = {
  input_count: "Входных материалов",
  relevant_count: "Релевантных",
  excluded_count: "Исключено",
  event_groups: "Групп событий",
  selected_count: "Выбранных событий",
  duration_ms: "Длительность, мс",
  model_calls: "Вызовов модели",
  tokens_used: "Использовано токенов",
  token_usage_available: "Учёт токенов доступен",
  cost_usd: "Стоимость, USD",
  mode: "Режим",
  model_attempts: "Попытки обращения к модели",
};
export default function Result() {
  return (
    <Suspense
      fallback={
        <div className="panel" role="status">
          Загрузка выпуска…
        </div>
      }
    >
      <RequestedResultPage />
    </Suspense>
  );
}
function RequestedResultPage() {
  const params = useSearchParams();
  const requestedId = params.get("id") || null;
  return (
    <ResultContent key={requestedId || "session"} requestedId={requestedId} />
  );
}
function ResultContent({ requestedId }: { requestedId: string | null }) {
  const { result: sessionResult, save } = useWorkspace();
  const [remote, setRemote] = useState<RequestedResult<DigestResult> | null>(
    null,
  );
  const [tab, setTab] = useState(0);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    if (!requestedId) return;
    const controller = new AbortController();
    request<DigestResult>(`/api/v1/digest/${encodeURIComponent(requestedId)}`, {
      signal: controller.signal,
    })
      .then((data) => {
        if (controller.signal.aborted) return;
        setRemote({ id: requestedId, status: "ready", result: data });
        if (data.digest_id === requestedId) save(data);
      })
      .catch((e) => {
        if (!controller.signal.aborted)
          setRemote({ id: requestedId, status: "error", error: e.message });
      });
    return () => controller.abort();
  }, [requestedId, save, retry]);
  const view = selectResultView(sessionResult, requestedId, remote);
  if (view.status === "loading")
    return (
      <>
        <PageHeading
          eyebrow="РЕЗУЛЬТАТ"
          title="Загрузка выпуска"
          description={`Запрошен выпуск: ${requestedId}`}
        />
        <div className="panel processing" role="status">
          <span className="spinner" />
          Получение результата из API…
        </div>
      </>
    );
  if (view.status === "empty" || view.status === "error")
    return (
      <>
        <PageHeading
          eyebrow="РЕЗУЛЬТАТ"
          title={view.status === "error" ? "Выпуск недоступен" : "Ваш выпуск"}
          description="Дайджест, источники и решения обработки в одном месте."
        />
        {view.status === "error" ? (
          <div className="panel">
            <Alert>{view.error}</Alert>
            <button
              className="button primary"
              onClick={() => {
                setRemote(null);
                setRetry((value) => value + 1);
              }}
            >
              Повторить загрузку
            </button>
            <Link href="/create/" className="button secondary">
              Создать новый выпуск
            </Link>
          </div>
        ) : (
          <EmptyResult />
        )}
      </>
    );
  const result = view.result;
  const copyText =
    tab === 2
      ? result.post_text
      : tab === 1
        ? `${result.email_subject}\n\n${result.digest_text}`
        : tab === 5
          ? JSON.stringify(result.journal, null, 2)
          : result.digest_text;
  async function copy() {
    try {
      await navigator.clipboard.writeText(copyText);
      setNotice("Текст скопирован");
      setError("");
    } catch {
      setError(
        "Браузер не разрешил копирование. Скачайте файл или выделите текст.",
      );
    }
  }
  return (
    <>
      <PageHeading
        eyebrow={`ВЫПУСК / ${result.digest_id}`}
        title={
          result.events.length ? "Выпуск подготовлен" : "Подходящих событий нет"
        }
        description={`${formatDate(result.period_start)} — ${formatDate(result.period_end)} · ${result.timezone}`}
        action={
          <Link href="/create/" className="button secondary">
            Новая обработка ↗
          </Link>
        }
      />
      <MetricGrid metrics={result.metrics} />
      <QualitySummary result={result} />
      <div className="result-toolbar">
        <button className="button primary" onClick={copy}>
          Скопировать
        </button>
        <button
          className="button secondary"
          onClick={() =>
            download(
              "digest.md",
              result.digest_text,
              "text/markdown;charset=utf-8",
            )
          }
        >
          Markdown ↓
        </button>
        <button
          className="button secondary"
          onClick={() =>
            download(
              "digest.json",
              JSON.stringify(result, null, 2),
              "application/json",
            )
          }
        >
          JSON ↓
        </button>
        <button
          className="button secondary"
          onClick={() =>
            download(
              "journal.csv",
              journalCsv(
                result.journal as unknown as Record<string, unknown>[],
              ),
              "text/csv;charset=utf-8",
            )
          }
        >
          CSV ↓
        </button>
        <button
          className="button secondary"
          onClick={() =>
            download(
              "email.html",
              result.email_preview_html,
              "text/html;charset=utf-8",
            )
          }
        >
          HTML письма ↓
        </button>
        <span className="copy-notice" role="status">
          {notice}
        </span>
      </div>
      {error && <Alert>{error}</Alert>}
      <div
        className="result-tabs"
        role="tablist"
        aria-label="Форматы и проверки"
      >
        {tabs.map((label, i) => (
          <button
            key={label}
            id={`tab-${i}`}
            role="tab"
            aria-selected={tab === i}
            aria-controls="result-panel"
            tabIndex={tab === i ? 0 : -1}
            onClick={() => setTab(i)}
            onKeyDown={(e) => {
              if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
                e.preventDefault();
                const next =
                  (tab + (e.key === "ArrowRight" ? 1 : -1) + tabs.length) %
                  tabs.length;
                setTab(next);
                document.getElementById(`tab-${next}`)?.focus();
              } else if (e.key === "Home" || e.key === "End") {
                e.preventDefault();
                const next = e.key === "Home" ? 0 : tabs.length - 1;
                setTab(next);
                document.getElementById(`tab-${next}`)?.focus();
              }
            }}
          >
            {label}
            {i === 3 && <span>{result.sources?.length || 0}</span>}
          </button>
        ))}
      </div>
      <section
        id="result-panel"
        role="tabpanel"
        aria-labelledby={`tab-${tab}`}
        className="result-content"
      >
        {tab === 0 && (
          <>
            <div className="section-heading">
              <h2>Главное за 24 часа</h2>
              <span>{result.event_count} СОБЫТИЙ</span>
            </div>
            {!result.events.length && (
              <Alert kind="warning">
                Подходящих событий нет. Причины исключения материалов доступны в
                журнале.
              </Alert>
            )}
            {result.events.map((event, i) => (
              <article className="event-card" key={event.event_id}>
                <div className="event-number">
                  {String(i + 1).padStart(2, "0")}
                </div>
                <div className="event-body">
                  <div className="event-meta">
                    <span className="tiny-label">{event.event_id}</span>
                    <span
                      className={`badge ${event.confidence === "high" ? "good" : ""}`}
                    >
                      Уверенность:{" "}
                      {{ high: "высокая", medium: "средняя", low: "низкая" }[
                        event.confidence
                      ] || event.confidence}
                    </span>
                    {event.is_preliminary && (
                      <span className="badge warning">
                        Предварительные данные
                      </span>
                    )}
                  </div>
                  <h3>{event.title}</h3>
                  <p>{event.summary}</p>
                  {event.consequences && (
                    <p className="consequences">
                      <strong>Последствия: </strong>
                      {event.consequences}
                    </p>
                  )}
                  {event.conflicts?.length > 0 && (
                    <Alert kind="warning">
                      <strong>Противоречия в источниках</strong>
                      <ul>
                        {event.conflicts.map((x, j) => (
                          <li key={j}>{x}</li>
                        ))}
                      </ul>
                    </Alert>
                  )}
                  <div className="event-sources">
                    {event.source_ids.map((id) => {
                      const source = selectEventSource(result, event, id);
                      return (
                        <SourceLink key={id} url={source?.url}>
                          {source?.source || "Источник не указан"} ·{" "}
                          {formatDate(source?.published_at || null)} · ID: {id}{" "}
                          · {source?.url || "URL отсутствует"}
                        </SourceLink>
                      );
                    })}
                  </div>
                  <details>
                    <summary>Факты и подтверждающие фрагменты</summary>
                    {event.evidence?.map((e, j) => (
                      <blockquote key={j}>
                        <p>{e.fragment}</p>
                        <SourceLink
                          url={
                            e.url ||
                            selectEventSource(result, event, e.source_id, e.url)
                              ?.url
                          }
                        >
                          {e.source_id}
                        </SourceLink>
                      </blockquote>
                    ))}
                    <p>
                      Организации:{" "}
                      {event.affected_entities?.join(", ") || "Данных нет"}
                    </p>
                    <p>
                      Системы:{" "}
                      {event.affected_systems?.join(", ") || "Данных нет"}
                    </p>
                    <p>
                      Сообщили: {event.reported_by?.join(", ") || "Данных нет"}
                    </p>
                  </details>
                </div>
              </article>
            ))}
            <details className="panel full-text">
              <summary>Полный текст для публикации</summary>
              <pre className="prose-text">{result.digest_text}</pre>
            </details>
          </>
        )}
        {tab === 1 && (
          <div className="panel">
            <div className="email-meta">
              <span className="tiny-label">ТЕМА ПИСЬМА</span>
              <h2>{result.email_subject}</h2>
              <p>
                Контрольное время: {formatDate(result.control_time)} · письмо не
                отправляется автоматически
              </p>
            </div>
            <iframe
              className="email-frame"
              title="Предпросмотр письма"
              srcDoc={`<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; img-src 'none'; form-action 'none'; base-uri 'none'">${result.email_preview_html}`}
              sandbox=""
              referrerPolicy="no-referrer"
            />
          </div>
        )}
        {tab === 2 && (
          <div className="panel">
            <div className="panel-heading">
              <h2>Готовый текст поста</h2>
              <span>ДО 2000 ЗНАКОВ БЕЗ URL</span>
            </div>
            <pre className="prose-text">{result.post_text}</pre>
            <button
              className="button secondary"
              onClick={() =>
                download(
                  "post.md",
                  result.post_text,
                  "text/markdown;charset=utf-8",
                )
              }
            >
              Скачать пост ↓
            </button>
          </div>
        )}
        {tab === 3 && (
          <div className="sources-list">
            {!result.sources.length && (
              <div className="panel empty-state">
                <h2>Источников в выпуске нет</h2>
                <p>
                  Причины исключения материалов доступны в журнале обработки.
                </p>
                <button className="button secondary" onClick={() => setTab(5)}>
                  Открыть журнал
                </button>
              </div>
            )}
            {result.sources?.map((s, i) => (
              <article className="panel source-card" key={`${s.id}-${i}`}>
                <span className="event-number">
                  {String(i + 1).padStart(2, "0")}
                </span>
                <div>
                  <span className="badge">
                    {sourceLabels[s.source_type || "unknown"] || s.source_type}
                  </span>
                  <h3>{s.title || "Без заголовка"}</h3>
                  <p>
                    {s.source || "Источник не указан"} ·{" "}
                    {formatDate(s.published_at)}
                  </p>
                  <SourceLink url={s.url}>
                    {s.url || "URL отсутствует"}
                  </SourceLink>
                  {s.url?.includes("example.org") && (
                    <small>Синтетический демонстрационный источник</small>
                  )}
                  <details>
                    <summary>Исходный текст</summary>
                    <p className="prose-text">
                      {s.text || "Текст отсутствует"}
                    </p>
                  </details>
                </div>
              </article>
            ))}
          </div>
        )}
        {tab === 4 && (
          <div className="selection-list">
            {!result.events.length && (
              <div className="panel empty-state">
                <h2>События не выбраны</h2>
                <p>
                  Проверьте причины исключения в журнале или загрузите другой
                  набор материалов.
                </p>
                <button className="button secondary" onClick={() => setTab(5)}>
                  Открыть журнал
                </button>
              </div>
            )}
            {result.events.map((e, i) => (
              <article key={e.event_id} className="panel">
                <div className="panel-heading">
                  <h3>
                    {String(i + 1).padStart(2, "0")} / {e.title}
                  </h3>
                </div>
                <p>{e.selection_reason}</p>
                <div className="ranking-factors">
                  {Object.entries(e.ranking_factors).map(([key, value]) => (
                    <div key={key}>
                      <span>{factorNames[key] || key}</span>
                      <strong>{value}</strong>
                    </div>
                  ))}
                </div>
                <p className="field-hint">
                  Основной источник: {e.primary_source_id || "Не указан"}. Место
                  события определяется сервером по указанным факторам.
                </p>
              </article>
            ))}
          </div>
        )}
        {tab === 5 && (
          <div className="panel">
            <Journal rows={result.journal} />
          </div>
        )}
        {tab === 6 && (
          <div className="panel">
            <div className="panel-heading">
              <h2>Проверки результата</h2>
              <span>
                {result.checks.filter((c) => c.passed).length} /{" "}
                {result.checks.length}
              </span>
            </div>
            {result.checks.map((c, i) => (
              <div className="check-row" key={i}>
                <span className={`check-icon ${c.passed ? "good" : "danger"}`}>
                  {c.passed ? "✓" : "!"}
                </span>
                <div>
                  <strong>{c.name}</strong>
                  <p>
                    {typeof c.details === "string"
                      ? c.details
                      : JSON.stringify(c.details)}
                  </p>
                </div>
                <span className={`badge ${c.passed ? "good" : "danger"}`}>
                  {c.passed ? "Пройдено" : "Не пройдено"}
                </span>
              </div>
            ))}
          </div>
        )}
        {tab === 7 && (
          <div className="panel">
            <h2>Паспорт запуска</h2>
            <dl className="run-metrics">
              {Object.entries(result.metrics).map(([k, v]) => (
                <div key={k}>
                  <dt>{metricNames[k] || k}</dt>
                  <dd>
                    {v != null && typeof v === "object" ? (
                      <pre className="code-block">
                        {JSON.stringify(v, null, 2)}
                      </pre>
                    ) : (
                      displayMetric(k, result.metrics)
                    )}
                  </dd>
                </div>
              ))}
              {[
                ["Модель", result.model_name],
                ["Версия модели", result.model_version],
                ["Промпт", result.prompt_version],
                ["Создано", formatDate(result.created_at)],
                ["Контрольное время", formatDate(result.control_time)],
              ].map(([k, v]) => (
                <div key={k}>
                  <dt>{k}</dt>
                  <dd>{v || "Нет данных"}</dd>
                </div>
              ))}
            </dl>
            {result.editorial_plan != null && (
              <details>
                <summary>Редакционный план модели</summary>
                <pre className="code-block">
                  {JSON.stringify(result.editorial_plan, null, 2)}
                </pre>
              </details>
            )}
          </div>
        )}
      </section>
    </>
  );
}
