import type { Article, JournalRow } from "./types";

type PreviewFailure = Pick<
  JournalRow,
  | "id"
  | "title"
  | "source"
  | "source_type"
  | "url"
  | "published_at"
  | "errors"
  | "exclusion_reason"
>;

export function preserveSourceErrors(
  articles: Article[],
  journal: PreviewFailure[],
): Article[] {
  return [
    ...articles,
    ...journal
      .filter((row) => row.errors.length > 0 || Boolean(row.exclusion_reason))
      .map((row, index) => ({
        id: row.id || `source-error-${index}`,
        title: row.title,
        source: row.source,
        source_type: row.source_type,
        url: row.url,
        published_at: row.published_at,
        text: null,
        read_error:
          row.errors.join("; ") || row.exclusion_reason || "Ошибка чтения",
      })),
  ];
}
