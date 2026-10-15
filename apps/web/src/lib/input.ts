import type { Article } from "./types.ts";
const fields = [
  "id",
  "title",
  "text",
  "source",
  "source_type",
  "url",
  "published_at",
] as const;
const maxSize = 2 * 1024 * 1024;
export function parseArticles(
  value: string,
  format: "json" | "csv" | "text",
): Article[] {
  if (new TextEncoder().encode(value).length > maxSize)
    throw new Error("Размер данных превышает 2 МБ.");
  if (!value.trim()) throw new Error("Добавьте материалы для обработки.");
  let records: unknown;
  if (format === "json") {
    try {
      records = JSON.parse(value);
    } catch {
      throw new Error("Не удалось прочитать JSON. Проверьте синтаксис.");
    }
  } else if (format === "csv") {
    const rows = csvRows(value.replace(/^\uFEFF/, ""));
    const headers = rows.shift()?.map((x) => x.trim());
    if (!headers?.includes("text") || !headers.includes("title"))
      throw new Error("CSV должен содержать колонки title и text.");
    records = rows
      .filter((row) => row.some((x) => x.trim()))
      .map((row) => {
        if (row.length !== headers.length)
          throw new Error("Количество колонок CSV не совпадает с заголовком.");
        return Object.fromEntries(headers.map((h, i) => [h, row[i]]));
      });
  } else records = [{ text: value }];
  if (!Array.isArray(records))
    throw new Error("JSON должен содержать массив публикаций.");
  if (!records.length) throw new Error("Набор публикаций пуст.");
  if (records.length > 100)
    throw new Error("В одном запуске допускается до 100 материалов.");
  return records.map((record) => {
    if (!record || typeof record !== "object" || Array.isArray(record))
      throw new Error("Каждая публикация должна быть объектом.");
    const input = record as Record<string, unknown>;
    return Object.fromEntries(
      fields.map((key) => {
        const v = input[key];
        if (v != null && typeof v !== "string")
          throw new Error(`Поле ${key} должно быть строкой или null.`);
        return [
          key,
          typeof v === "string" && v.trim()
            ? key === "text"
              ? v
              : v.trim()
            : null,
        ];
      }),
    ) as Article;
  });
}
function csvRows(value: string): string[][] {
  const rows: string[][] = [];
  let row: string[] = [];
  let cell = "";
  let quoted = false;
  for (let i = 0; i < value.length; i++) {
    const ch = value[i];
    if (ch === '"') {
      if (quoted && value[i + 1] === '"') {
        cell += '"';
        i++;
      } else quoted = !quoted;
    } else if (ch === "," && !quoted) {
      row.push(cell);
      cell = "";
    } else if ((ch === "\n" || ch === "\r") && !quoted) {
      if (ch === "\r" && value[i + 1] === "\n") i++;
      row.push(cell);
      rows.push(row);
      row = [];
      cell = "";
    } else cell += ch;
  }
  if (quoted) throw new Error("В CSV не закрыты кавычки.");
  row.push(cell);
  rows.push(row);
  return rows;
}
export function controlTime(date: string, time: string): string {
  const result = `${date}T${time}:00+03:00`;
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date) || !/^\d{2}:\d{2}$/.test(time))
    throw new Error("Укажите дату и время.");
  if (Number(time.slice(0, 2)) > 23 || Number(time.slice(3, 5)) > 59)
    throw new Error("Некорректная дата или время.");
  const parsed = new Date(result);
  if (
    !Number.isFinite(parsed.getTime()) ||
    new Date(`${date}T00:00:00Z`).toISOString().slice(0, 10) !== date
  )
    throw new Error("Некорректная дата или время.");
  return result;
}
export function safeUrl(value: string | null | undefined): string | null {
  try {
    const u = new URL(value || "");
    return ["https:", "http:"].includes(u.protocol) ? u.href : null;
  } catch {
    return null;
  }
}
export function journalCsv(rows: Record<string, unknown>[]): string {
  const columns = Array.from(new Set(rows.flatMap((row) => Object.keys(row))));
  const escape = (value: unknown) => {
    let s =
      typeof value === "object" && value !== null
        ? JSON.stringify(value)
        : String(value ?? "");
    if (/^[\s]*[=+@-]/.test(s)) s = "'" + s;
    return '"' + s.replaceAll('"', '""') + '"';
  };
  return (
    "\uFEFF" +
    [
      columns.map(escape).join(","),
      ...rows.map((row) => columns.map((key) => escape(row[key])).join(",")),
    ].join("\r\n")
  );
}
export function download(name: string, text: string, type: string) {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
export function moscowNow(): { date: string; time: string } {
  const parts = new Intl.DateTimeFormat("sv-SE", {
    timeZone: "Europe/Moscow",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).format(new Date());
  return { date: parts.slice(0, 10), time: parts.slice(11, 16) };
}
export function formatDate(value: string | null | undefined): string {
  if (!value) return "Дата не подтверждена";
  const d = new Date(value);
  return Number.isFinite(d.getTime())
    ? new Intl.DateTimeFormat("ru-RU", {
        timeZone: "Europe/Moscow",
        dateStyle: "medium",
        timeStyle: "short",
      }).format(d)
    : "Некорректная дата";
}
