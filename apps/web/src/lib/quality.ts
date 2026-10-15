import type { DigestResult } from "./types";

export function displayMetric(
  key: string,
  metrics: Record<string, unknown>,
): string {
  if (
    (key === "tokens_used" && metrics.token_usage_available === false) ||
    (key === "cost_usd" && metrics[key] == null)
  )
    return "Недоступно";
  return metrics[key] == null ? "Нет данных" : String(metrics[key]);
}

export function textLength(text: string) {
  return {
    total: Array.from(text).length,
    withoutUrls: Array.from(text.replace(/https?:\/\/\S+/g, "")).length,
  };
}

export function summarizeQuality(result: {
  checks: DigestResult["checks"];
  events: Pick<
    DigestResult["events"][number],
    "is_preliminary" | "conflicts"
  >[];
  warnings: string[];
}) {
  return {
    checksPassed: result.checks.filter((check) => check.passed).length,
    checksTotal: result.checks.length,
    failedChecks: result.checks
      .filter((check) => !check.passed)
      .map((check) => check.name),
    preliminaryEvents: result.events.filter((event) => event.is_preliminary)
      .length,
    conflictingEvents: result.events.filter(
      (event) => event.conflicts?.length > 0,
    ).length,
    warningCount: result.warnings.length,
  };
}
