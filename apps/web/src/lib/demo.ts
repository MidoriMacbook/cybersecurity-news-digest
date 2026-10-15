import { request } from "./api.ts";
import type { Article } from "./types";

export const demoScenarios = [
  {
    id: "sample_news",
    label: "Пример новостей",
    description: "Обычный выпуск из учебных публикаций.",
  },
  {
    id: "duplicate_event",
    label: "Повторы одного события",
    description: "Несколько источников должны объединиться в одно событие.",
  },
  {
    id: "no_relevant_news",
    label: "Нет релевантных новостей",
    description: "Проверка пустого выпуска и причин исключения.",
  },
  {
    id: "incomplete_article",
    label: "Неполная публикация",
    description: "Проверка пропущенных полей и недостаточного текста.",
  },
  {
    id: "conflicting_sources",
    label: "Противоречия источников",
    description: "Расхождения должны остаться видимыми в результате.",
  },
  {
    id: "unavailable_sources",
    label: "Недоступные источники",
    description: "Проверка обработки материалов без доступного источника.",
  },
  {
    id: "prompt_injection",
    label: "Посторонние инструкции",
    description: "Инструкции внутри публикации не должны управлять редакцией.",
  },
] as const;
export type DemoScenario = (typeof demoScenarios)[number]["id"];
export type DemoData = {
  articles: Article[];
  control_time: string;
  scenario?: string;
  description?: string;
};

export function loadDemoScenario(
  scenario: DemoScenario,
  fetcher: typeof fetch = fetch,
): Promise<DemoData> {
  return request<DemoData>(
    `/api/v1/demo?scenario=${encodeURIComponent(scenario)}`,
    {},
    fetcher,
  );
}
