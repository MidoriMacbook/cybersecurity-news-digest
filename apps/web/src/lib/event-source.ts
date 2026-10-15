import type { Article, DigestEvent, JournalRow } from "./types";

type EventSourceResult = {
  sources: Article[];
  journal: Pick<JournalRow, "id" | "event_id">[];
};

/** Sources and journal preserve the same input order; IDs alone are not unique. */
export function selectEventSource(
  result: EventSourceResult,
  event: Pick<DigestEvent, "event_id" | "evidence">,
  sourceId: string,
  evidenceUrl?: string | null,
): Article | undefined {
  const candidates = result.sources.filter((source, index) => {
    const row = result.journal[index];
    return (
      source.id === sourceId &&
      !source.read_error &&
      row?.id === sourceId &&
      row.event_id === event.event_id
    );
  });
  if (evidenceUrl)
    return candidates.find((source) => source.url === evidenceUrl);
  const evidenceUrls = new Set(
    event.evidence
      .filter((evidence) => evidence.source_id === sourceId && evidence.url)
      .map((evidence) => evidence.url),
  );
  return (
    candidates.find((source) => evidenceUrls.has(source.url)) || candidates[0]
  );
}
