"use client";
import { useMemo, useState } from "react";
import { formatDate, safeUrl } from "../lib/input";
import type { JournalRow } from "../lib/types";
export const statusLabels: Record<string, string> = {
  accepted: "Принят",
  included_in_digest: "В дайджесте",
  excluded_irrelevant: "Вне темы",
  excluded_outside_period: "Вне периода",
  excluded_unknown_date: "Неизвестная дата",
  grouped_duplicate: "Объединён",
  insufficient_text: "Недостаточно текста",
  source_unavailable: "Источник недоступен",
  parse_error: "Ошибка разбора",
  validation_failed: "Ошибка проверки",
};
export const sourceLabels: Record<string, string> = {
  media: "СМИ",
  author: "Автор",
  vendor: "Вендор",
  regulator: "Регулятор",
  official: "Официальный",
  unknown: "Неизвестный",
};
export function SourceLink({
  url,
  children,
}: {
  url: string | null | undefined;
  children: React.ReactNode;
}) {
  const safe = safeUrl(url);
  return safe ? (
    <a
      href={safe}
      target="_blank"
      rel="noopener noreferrer"
      className="text-link"
    >
      {children} ↗
    </a>
  ) : (
    <span>{children}</span>
  );
}
export function Journal({ rows }: { rows: JournalRow[] }) {
  const [status, setStatus] = useState("");
  const [reason, setReason] = useState("");
  const [group, setGroup] = useState("");
  const [type, setType] = useState("");
  const [error, setError] = useState("");
  const [date, setDate] = useState("");
  const filtered = useMemo(
    () =>
      rows.filter(
        (r) =>
          (!status || r.status === status) &&
          (!reason || r.exclusion_reason === reason) &&
          (!group || r.event_id === group) &&
          (!type || r.source_type === type) &&
          (!error ||
            (error === "yes" ? r.errors?.length : !r.errors?.length)) &&
          (!date ||
            (r.published_at &&
              Number.isFinite(new Date(r.published_at).getTime()) &&
              new Intl.DateTimeFormat("sv-SE", {
                timeZone: "Europe/Moscow",
              }).format(new Date(r.published_at)) === date)),
      ),
    [rows, status, reason, group, type, error, date],
  );
  const unique = (
    key: "status" | "exclusion_reason" | "event_id" | "source_type",
  ) =>
    Array.from(
      new Set(rows.map((r) => r[key]).filter((v): v is string => Boolean(v))),
    );
  return (
    <>
      <div className="journal-filters">
        <label className="field">
          Статус
          <select value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">Все статусы</option>
            {unique("status").map((s) => (
              <option key={s} value={s}>
                {statusLabels[s] || s}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          Причина исключения
          <select value={reason} onChange={(e) => setReason(e.target.value)}>
            <option value="">Все причины</option>
            {unique("exclusion_reason").map((s) => (
              <option key={s}>{s}</option>
            ))}
          </select>
        </label>
        <label className="field">
          Группа события
          <select value={group} onChange={(e) => setGroup(e.target.value)}>
            <option value="">Все группы</option>
            {unique("event_id").map((s) => (
              <option key={s}>{s}</option>
            ))}
          </select>
        </label>
        <label className="field">
          Тип источника
          <select value={type} onChange={(e) => setType(e.target.value)}>
            <option value="">Все типы</option>
            {unique("source_type").map((s) => (
              <option value={s} key={s}>
                {sourceLabels[s] || s}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          Ошибка
          <select value={error} onChange={(e) => setError(e.target.value)}>
            <option value="">Любое состояние</option>
            <option value="yes">Есть ошибки</option>
            <option value="no">Без ошибок</option>
          </select>
        </label>
        <label className="field">
          Дата публикации
          <input
            type="date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
          />
        </label>
      </div>
      <div className="journal-count">
        Показано {filtered.length} из {rows.length}
        <button
          type="button"
          className="text-link"
          onClick={() => {
            setStatus("");
            setReason("");
            setGroup("");
            setType("");
            setError("");
            setDate("");
          }}
        >
          Сбросить фильтры
        </button>
      </div>
      <div className="table-scroll">
        <table className="journal-table">
          <thead>
            <tr>
              <th>Материал / источник</th>
              <th>Дата · Москва</th>
              <th>Статус</th>
              <th>Решение обработки</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((r, i) => (
              <tr key={`${r.id}-${i}`}>
                <td>
                  <strong>{r.title || "Без заголовка"}</strong>
                  <small>
                    <SourceLink url={r.url}>
                      {r.source || "Источник не указан"}
                    </SourceLink>{" "}
                    ·{" "}
                    {sourceLabels[r.source_type || "unknown"] || r.source_type}
                  </small>
                  <code>{r.id}</code>
                </td>
                <td>{formatDate(r.published_at)}</td>
                <td>
                  <span
                    className={`badge ${r.status === "included_in_digest" ? "good" : r.errors?.length ? "danger" : ""}`}
                  >
                    {statusLabels[r.status] || r.status}
                  </span>
                  {r.event_id && <small>{r.event_id}</small>}
                </td>
                <td>
                  {r.exclusion_reason ||
                    r.inclusion_reason ||
                    "Причина не указана"}
                  <details>
                    <summary>Проверки и детали</summary>
                    <dl>
                      <dt>Пропуски</dt>
                      <dd>{r.missing_fields?.join(", ") || "Нет"}</dd>
                      <dt>Ошибки</dt>
                      <dd>{r.errors?.join("; ") || "Нет"}</dd>
                      <dt>Предупреждения</dt>
                      <dd>{r.warnings?.join("; ") || "Нет"}</dd>
                      <dt>Релевантность</dt>
                      <dd>{JSON.stringify(r.relevance)}</dd>
                      <dt>Период</dt>
                      <dd>{JSON.stringify(r.period_check)}</dd>
                      <dt>Факты</dt>
                      <dd>{JSON.stringify(r.fact_check)}</dd>
                      <dt>Модель / промпт</dt>
                      <dd>
                        {r.model_name} / {r.prompt_version}
                      </dd>
                      <dt>Обработано</dt>
                      <dd>{formatDate(r.processed_at)}</dd>
                    </dl>
                  </details>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!filtered.length && (
          <p className="empty-filter">По заданным фильтрам материалов нет.</p>
        )}
      </div>
    </>
  );
}
