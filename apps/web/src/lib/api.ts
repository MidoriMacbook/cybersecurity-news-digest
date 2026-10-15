export const apiBase = (process.env.NEXT_PUBLIC_API_URL || "").replace(
  /\/$/,
  "",
);
export async function request<T>(
  path: string,
  options: RequestInit = {},
  fetcher: typeof fetch = fetch,
): Promise<T> {
  let response: Response;
  try {
    response = await fetcher(apiBase + path, {
      ...options,
      headers: { "Content-Type": "application/json", ...options.headers },
      signal: options.signal
        ? AbortSignal.any([options.signal, AbortSignal.timeout(120000)])
        : AbortSignal.timeout(120000),
    });
  } catch (error) {
    if (error instanceof Error && error.name === "AbortError")
      throw new Error("Запрос отменён.");
    if (error instanceof Error && error.name === "TimeoutError")
      throw new Error("API не ответил за 120 секунд. Повторите запрос позже.");
    throw new Error(
      "Не удалось соединиться с API. Проверьте подключение или повторите запрос: бесплатный сервер может запускаться после сна.",
    );
  }
  let data: unknown;
  try {
    data = await response.json();
  } catch {
    throw new Error(
      `API вернул нечитаемый ответ (${response.status}). Повторите запрос позже.`,
    );
  }
  if (!response.ok) {
    const detail = (data as { detail?: unknown })?.detail;
    const message = Array.isArray(detail)
      ? detail
          .map((x) => {
            const e = x as { loc?: string[]; msg?: string };
            return `${e.loc?.join(".") || ""}: ${e.msg || "ошибка"}`;
          })
          .join("; ")
      : typeof detail === "string"
        ? detail
        : `Ошибка API (${response.status}).`;
    throw new Error(message);
  }
  return data as T;
}
