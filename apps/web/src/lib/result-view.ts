export type RequestedResult<T> =
  | { id: string; status: "ready"; result: T }
  | { id: string; status: "error"; error: string };
export type ResultView<T> =
  | { status: "loading" }
  | { status: "empty" }
  | { status: "error"; error: string }
  | { status: "ready"; result: T };

export function selectResultView<T extends { digest_id: string }>(
  session: T | null,
  requestedId: string | null,
  remote: RequestedResult<T> | null,
): ResultView<T> {
  if (!requestedId)
    return session ? { status: "ready", result: session } : { status: "empty" };
  if (!remote || remote.id !== requestedId) return { status: "loading" };
  if (remote.status === "error")
    return { status: "error", error: remote.error };
  if (remote.result.digest_id !== requestedId)
    return {
      status: "error",
      error: "API вернул другой выпуск. Повторите запрос.",
    };
  return { status: "ready", result: remote.result };
}
