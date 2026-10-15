"use client";
/* Browser time/query initialize after static hydration to avoid mismatched HTML. */
/* eslint-disable react-hooks/set-state-in-effect */
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Alert, PageHeading, useWorkspace } from "../../components/workspace";
import { request } from "../../lib/api";
import { Journal, sourceLabels } from "../../components/journal";
import {
  controlTime,
  moscowNow,
  parseArticles,
  serializeDigestRequest,
} from "../../lib/input";
import { serverModeLabel } from "../../lib/execution";
import type { Article, DigestResult, JournalRow } from "../../lib/types";
import { demoScenarios, loadDemoScenario } from "../../lib/demo";
import type { DemoScenario } from "../../lib/demo";
import { textLength } from "../../lib/quality";
import { preserveSourceErrors } from "../../lib/source-errors";
type SourceMode = "json" | "csv" | "text" | "demo" | "remote";
const modes: { id: SourceMode; label: string }[] = [
  { id: "json", label: "JSON" },
  { id: "csv", label: "CSV" },
  { id: "text", label: "Текст" },
  { id: "demo", label: "Демо-набор" },
  { id: "remote", label: "RSS / HTML" },
];
export default function Create() {
  const { save, health } = useWorkspace();
  const router = useRouter();
  const [mode, setMode] = useState<SourceMode>("json");
  const [raw, setRaw] = useState("");
  const [date, setDate] = useState("");
  const [time, setTime] = useState("");
  const [limit, setLimit] = useState(5);
  const [useAi, setUseAi] = useState(false);
  const [articles, setArticles] = useState<Article[]>([]);
  const [urls, setUrls] = useState("");
  const [warnings, setWarnings] = useState<string[]>([]);
  const [previewJournal, setPreviewJournal] = useState<JournalRow[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [title, setTitle] = useState("");
  const [articleId, setArticleId] = useState("");
  const [sourceType, setSourceType] = useState("");
  const [source, setSource] = useState("");
  const [url, setUrl] = useState("");
  const [published, setPublished] = useState("");
  const [scenario, setScenario] = useState<DemoScenario>("sample_news");
  const [demoDescription, setDemoDescription] = useState("");
  const [loaded, setLoaded] = useState(false);
  const controller = useRef<AbortController | null>(null);
  useEffect(() => {
    const now = moscowNow();
    setDate(now.date);
    setTime(now.time);
    if (new URLSearchParams(window.location.search).get("demo") === "1") {
      setMode("demo");
      setLoading(true);
      loadDemoScenario("sample_news")
        .then((data) => {
          setArticles(data.articles);
          setDate(data.control_time.slice(0, 10));
          setTime(data.control_time.slice(11, 16));
          setDemoDescription(data.description || demoScenarios[0].description);
          setLoaded(true);
        })
        .catch((e) => setError(e.message))
        .finally(() => setLoading(false));
    }
  }, []);
  useEffect(() => {
    if (!busy) return;
    const started = Date.now();
    const interval = setInterval(
      () => setElapsed(Math.floor((Date.now() - started) / 1000)),
      1000,
    );
    return () => clearInterval(interval);
  }, [busy]);
  useEffect(() => () => controller.current?.abort(), []);
  async function loadDemo() {
    setLoading(true);
    setError("");
    setArticles([]);
    setLoaded(false);
    try {
      const data = await loadDemoScenario(scenario);
      setArticles(data.articles);
      setDate(data.control_time.slice(0, 10));
      setTime(data.control_time.slice(11, 16));
      setDemoDescription(
        data.description ||
          demoScenarios.find((s) => s.id === scenario)!.description,
      );
      setLoaded(true);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }
  async function preview() {
    setLoading(true);
    setError("");
    setArticles([]);
    setWarnings([]);
    setPreviewJournal([]);
    setLoaded(false);
    try {
      const data = await request<{
        articles: Article[];
        warnings: string[];
        journal: JournalRow[];
      }>("/api/v1/sources/preview", {
        method: "POST",
        body: JSON.stringify({
          urls: urls
            .split(/\n/)
            .map((x) => x.trim())
            .filter(Boolean),
        }),
      });
      setArticles(data.articles);
      setWarnings(data.warnings || []);
      setPreviewJournal(data.journal || []);
      setLoaded(true);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }
  async function fileInput(file: File | undefined) {
    if (!file) return;
    setError("");
    if (file.size > 2_000_000) {
      setError("Максимальный размер файла — 2 МБ.");
      return;
    }
    try {
      setRaw(await file.text());
    } catch {
      setError("Не удалось прочитать файл.");
    }
  }
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setElapsed(0);
    try {
      const control = controlTime(date, time);
      let input = articles;
      if (mode === "remote")
        input = preserveSourceErrors(articles, previewJournal);
      if (mode === "json" || mode === "csv") input = parseArticles(raw, mode);
      if (mode === "text") {
        input = parseArticles(raw, "text").map((a) => ({
          ...a,
          id: articleId.trim() || null,
          source_type: sourceType || null,
          title: title.trim() || null,
          source: source.trim() || null,
          url: url.trim() || null,
          published_at: published.trim() || null,
          original_record: {
            id: articleId,
            title,
            text: raw,
            source,
            source_type: sourceType,
            url,
            published_at: published,
          },
        }));
      }
      if (!input.length)
        throw new Error(
          "Загрузите набор или получите предпросмотр источников.",
        );
      setBusy(true);
      controller.current = new AbortController();
      const result = await request<DigestResult>("/api/v1/digest", {
        method: "POST",
        body: serializeDigestRequest({
          control_time: control,
          timezone: "Europe/Moscow",
          event_limit: limit,
          use_ai: useAi,
          articles: input,
        }),
        signal: controller.current.signal,
      });
      save(result);
      router.push("/result/");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <PageHeading
        eyebrow="НОВЫЙ ВЫПУСК"
        title="Создать дайджест"
        description="Добавьте материалы и задайте период. Все решения обработки будут доступны в журнале."
      />
      <form onSubmit={submit}>
        <div className="create-grid">
          <div className="panel input-panel">
            <div className="panel-heading">
              <h2>
                <span className="step">01</span> Материалы
              </h2>
              <span>ДО 100 ПУБЛИКАЦИЙ · 2 МБ</span>
            </div>
            <div className="source-tabs" aria-label="Источник данных">
              {modes.map((m) => (
                <button
                  type="button"
                  className={mode === m.id ? "selected" : ""}
                  key={m.id}
                  disabled={busy || loading}
                  onClick={() => {
                    setMode(m.id);
                    setArticles([]);
                    setWarnings([]);
                    setPreviewJournal([]);
                    setError("");
                    setLoaded(false);
                    setDemoDescription("");
                  }}
                  aria-pressed={mode === m.id}
                >
                  {m.label}
                </button>
              ))}
            </div>
            {(mode === "json" || mode === "csv") && (
              <>
                <label className="file-drop">
                  Загрузить {mode.toUpperCase()}
                  <span>Выберите файл или вставьте данные ниже</span>
                  <input
                    type="file"
                    accept={
                      mode === "json"
                        ? ".json,application/json"
                        : ".csv,text/csv"
                    }
                    onChange={(e) => fileInput(e.target.files?.[0])}
                    disabled={busy}
                  />
                </label>
                <label className="field">
                  Данные {mode.toUpperCase()}
                  <textarea
                    value={raw}
                    onChange={(e) => setRaw(e.target.value)}
                    className="code-input"
                    placeholder={
                      mode === "json"
                        ? '[\n  {\n    "title": "Заголовок публикации",\n    "text": "Подтверждённые факты…",\n    "published_at": "2026-10-14T10:30:00+03:00"\n  }\n]'
                        : "id,title,text,source,source_type,url,published_at"
                    }
                    rows={12}
                    disabled={busy}
                  />
                </label>
                <p className="field-hint">
                  Введено {textLength(raw).total.toLocaleString("ru-RU")}{" "}
                  знаков. Отсутствующие поля сохраняются как null. URL и даты не
                  восстанавливаются автоматически.
                </p>
              </>
            )}
            {mode === "text" && (
              <>
                <div className="field-pair">
                  <label className="field">
                    ID публикации
                    <input
                      value={articleId}
                      onChange={(e) => setArticleId(e.target.value)}
                      placeholder="Идентификатор из вашего набора"
                    />
                  </label>
                  <label className="field">
                    Тип источника
                    <select
                      value={sourceType}
                      onChange={(e) => setSourceType(e.target.value)}
                    >
                      <option value="">Не указан (null)</option>
                      {Object.entries(sourceLabels).map(([key, label]) => (
                        <option key={key} value={key}>
                          {label}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
                <div className="field-pair">
                  <label className="field">
                    Заголовок
                    <input
                      value={title}
                      onChange={(e) => setTitle(e.target.value)}
                    />
                  </label>
                  <label className="field">
                    Источник
                    <input
                      value={source}
                      onChange={(e) => setSource(e.target.value)}
                    />
                  </label>
                </div>
                <label className="field">
                  URL публикации
                  <input
                    type="url"
                    value={url}
                    onChange={(e) => setUrl(e.target.value)}
                    placeholder="https://…"
                  />
                </label>
                <label className="field">
                  Дата публикации с часовым поясом
                  <input
                    value={published}
                    onChange={(e) => setPublished(e.target.value)}
                    placeholder="2026-10-14T10:30:00+03:00"
                  />
                </label>
                <label className="field">
                  Полный текст публикации
                  <textarea
                    rows={9}
                    value={raw}
                    onChange={(e) => setRaw(e.target.value)}
                  />
                </label>
                <p className="field-hint">
                  Введено {textLength(raw).total.toLocaleString("ru-RU")} / 30
                  000 знаков. Для включения нужны ID, заголовок, источник, URL,
                  подтверждённая дата и полный текст. Пропущенные значения
                  сохраняются как null и отражаются в журнале.
                </p>
              </>
            )}
            {mode === "demo" && (
              <div className="demo-upload">
                <span className="demo-icon" aria-hidden="true">
                  ◈
                </span>
                <h3>Учебные сценарии</h3>
                <p>
                  Синтетические публикации: повторы, противоречия, неизвестные
                  даты и посторонние инструкции. Ссылки example.org —
                  демонстрационные.
                </p>
                <label className="field demo-choice">
                  Сценарий проверки
                  <select
                    value={scenario}
                    disabled={busy || loading}
                    onChange={(e) => {
                      setScenario(e.target.value as DemoScenario);
                      setArticles([]);
                      setLoaded(false);
                      setDemoDescription("");
                      setError("");
                    }}
                  >
                    {demoScenarios.map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.label}
                      </option>
                    ))}
                  </select>
                  <span className="field-hint">
                    {demoScenarios.find((s) => s.id === scenario)?.description}
                  </span>
                </label>
                <button
                  type="button"
                  className="button secondary"
                  onClick={loadDemo}
                  disabled={loading || busy}
                >
                  {loading ? "Загрузка…" : "Загрузить демо-набор"}
                </button>
                {loaded && (
                  <p className="demo-description" role="status">
                    {demoDescription} Загружено материалов: {articles.length}.
                    Контрольное время установлено по сценарию.
                  </p>
                )}
              </div>
            )}
            {mode === "remote" && (
              <>
                <label className="field">
                  Адреса RSS или HTML, по одному на строку
                  <textarea
                    rows={6}
                    value={urls}
                    onChange={(e) => {
                      setUrls(e.target.value);
                      setArticles([]);
                      setLoaded(false);
                      setPreviewJournal([]);
                      setWarnings([]);
                    }}
                    placeholder="https://www.cisa.gov/…"
                    disabled={loading || busy}
                  />
                </label>
                <button
                  type="button"
                  className="button secondary"
                  onClick={preview}
                  disabled={loading || busy || !urls.trim()}
                >
                  {loading ? "Получение источников…" : "Получить предпросмотр"}
                </button>
                <p className="field-hint">
                  До 5 адресов. API проверит их доступность. Поддерживаются
                  cisa.gov, www.cisa.gov и nvd.nist.gov; другие домены зависят
                  от настроек сервера. Причины отказа будут доступны в журнале.
                </p>
              </>
            )}
            {loading && (
              <div className="loading-preview" role="status">
                <span className="spinner" aria-hidden="true" />
                <span>Получаем материалы из API…</span>
                <div className="skeleton-line" />
                <div className="skeleton-line short" />
              </div>
            )}
            {loaded && !loading && !articles.length && (
              <Alert kind="warning">
                Материалы не получены. Проверьте предупреждения и журнал или
                загрузите другой сценарий.
              </Alert>
            )}
            {articles.length > 0 && (
              <div className="preview-list">
                <div className="eyebrow">
                  ЗАГРУЖЕНО: {articles.length} МАТЕРИАЛОВ
                </div>
                {articles.slice(0, 5).map((a, i) => (
                  <div key={i}>
                    <span>{String(i + 1).padStart(2, "0")}</span>
                    <p>
                      {a.title || "Без заголовка"}
                      <small>{a.source || "Источник не указан"}</small>
                    </p>
                  </div>
                ))}
                {articles.length > 5 && (
                  <small>И ещё {articles.length - 5} материалов</small>
                )}
              </div>
            )}
          </div>
          <aside className="panel settings-panel">
            <div className="panel-heading">
              <h2>
                <span className="step">02</span> Параметры
              </h2>
            </div>
            <label className="field">
              Контрольная дата
              <input
                type="date"
                required
                value={date}
                onChange={(e) => setDate(e.target.value)}
                disabled={busy}
              />
            </label>
            <label className="field">
              Контрольное время
              <input
                type="time"
                required
                value={time}
                onChange={(e) => setTime(e.target.value)}
                disabled={busy}
              />
            </label>
            <label className="field">
              Часовой пояс
              <select value="Europe/Moscow" disabled>
                <option>Europe/Moscow</option>
              </select>
              <span className="field-hint">
                Последние 24 часа до заданного времени, UTC+3.
              </span>
            </label>
            <label className="field">
              Лимит событий
              <select
                value={limit}
                onChange={(e) => setLimit(Number(e.target.value))}
                disabled={busy}
              >
                {[1, 2, 3, 4, 5].map((n) => (
                  <option key={n} value={n}>
                    {n} {n === 1 ? "событие" : n === 5 ? "событий" : "события"}
                  </option>
                ))}
              </select>
            </label>
            <label className="toggle-field">
              <input
                type="checkbox"
                checked={useAi}
                onChange={(e) => setUseAi(e.target.checked)}
                disabled={busy}
              />
              <span>
                <strong>Использовать ИИ</strong>
                <small>
                  Оценка темы, объединение событий, порядок и выбор фрагментов.
                  Источники и факты проверяются отдельно.
                </small>
              </span>
            </label>
            <div className="settings-note">
              {health
                ? `Сервер: ${serverModeLabel(health)}.`
                : "Режим определяется сервером."}{" "}
              Без ключа доступна локальная обработка.
            </div>
            <button
              className="button primary wide"
              disabled={busy || loading}
              type="submit"
            >
              {busy ? "Обработка…" : "Подготовить выпуск →"}
            </button>
          </aside>
        </div>
        {error && (
          <Alert>
            {error}{" "}
            <span>
              Исправьте данные или повторите загрузку выбранного источника.
            </span>
          </Alert>
        )}
        {warnings.length > 0 && (
          <Alert kind="warning">
            <strong>Предупреждения источников: {warnings.length}</strong>
            <ul>
              {warnings.map((w, i) => (
                <li key={i}>{w}</li>
              ))}
            </ul>
          </Alert>
        )}
        {previewJournal.length > 0 && (
          <div className="panel">
            <h2>Журнал получения источников</h2>
            <Journal rows={previewJournal} />
          </div>
        )}
        {busy && (
          <div className="panel processing" role="status" aria-live="polite">
            <span className="spinner" />
            <div>
              <strong>Материалы обрабатываются · {elapsed} с</strong>
              <p>
                API проверяет период, факты и группы событий. Итоговые метрики
                появятся после ответа сервера.
              </p>
            </div>
            <button
              type="button"
              className="button secondary"
              onClick={() => controller.current?.abort()}
            >
              Отменить
            </button>
          </div>
        )}
      </form>
    </>
  );
}
