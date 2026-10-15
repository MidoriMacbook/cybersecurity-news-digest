"use client";
import { Journal } from "../../components/journal";
import {
  EmptyResult,
  PageHeading,
  useWorkspace,
} from "../../components/workspace";
import { download, journalCsv } from "../../lib/input";
export default function JournalPage() {
  const { result } = useWorkspace();
  return (
    <>
      <PageHeading
        eyebrow="АУДИТ ОБРАБОТКИ"
        title="Журнал материалов"
        description="Проверьте, почему материал включён, объединён или исключён из выпуска."
        action={
          result ? (
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
              Экспорт CSV ↓
            </button>
          ) : undefined
        }
      />
      {result ? (
        <div className="panel">
          <Journal rows={result.journal} />
        </div>
      ) : (
        <EmptyResult />
      )}
    </>
  );
}
