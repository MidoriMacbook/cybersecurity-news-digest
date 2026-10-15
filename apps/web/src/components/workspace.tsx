"use client";
/* Browser session hydration needs one effect after static export hydration. */
/* eslint-disable react-hooks/set-state-in-effect */
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import { request } from "../lib/api";
import type { DigestResult, Health } from "../lib/types";
import { serverModeLabel } from "../lib/execution";

const Context = createContext<{
  result: DigestResult | null;
  save: (r: DigestResult) => void;
  health: Health | null;
  healthError: string;
  ready: boolean;
}>({
  result: null,
  save: () => {},
  health: null,
  healthError: "",
  ready: false,
});
export function useWorkspace() {
  return useContext(Context);
}
export function Workspace({ children }: { children: React.ReactNode }) {
  const [result, setResult] = useState<DigestResult | null>(null);
  const [ready, setReady] = useState(false);
  const [health, setHealth] = useState<Health | null>(null);
  const [healthError, setHealthError] = useState("");
  const path = usePathname();
  useEffect(() => {
    try {
      const value = sessionStorage.getItem("cyberdigest.result");
      if (value) {
        const stored = JSON.parse(value) as DigestResult;
        if (
          stored.digest_id &&
          Array.isArray(stored.events) &&
          Array.isArray(stored.journal)
        )
          setResult(stored);
      }
    } catch {
      sessionStorage.removeItem("cyberdigest.result");
    }
    setReady(true);
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    request<Health>("/health", { signal: controller.signal, cache: "no-store" })
      .then((value) => {
        if (!controller.signal.aborted) {
          setHealth(value);
          setHealthError("");
        }
      })
      .catch((error) => {
        if (!controller.signal.aborted) {
          setHealth(null);
          setHealthError(error.message);
        }
      });
    return () => controller.abort();
  }, [path, result?.digest_id]);
  const save = useCallback((r: DigestResult) => {
    setResult(r);
    try {
      sessionStorage.setItem("cyberdigest.result", JSON.stringify(r));
    } catch {
      /* The current result remains available when storage quota is exceeded. */
    }
  }, []);
  const links = [
    ["/", "Обзор", "01"],
    ["/create/", "Создать дайджест", "02"],
    ["/result/", "Результат", "03"],
    ["/journal/", "Журнал обработки", "04"],
    ["/docs/", "Документация", "05"],
  ];
  return (
    <Context.Provider value={{ result, save, health, healthError, ready }}>
      <a href="#content" className="skip-link">
        Перейти к содержимому
      </a>
      <div className="workspace">
        <aside className="sidebar">
          <Link href="/" className="brand">
            <span className="brand-mark" aria-hidden="true">
              КД<span>·</span>
            </span>
            <span>
              Кибердайджест<small>РЕДАКЦИЯ БЕЗОПАСНОСТИ</small>
            </span>
          </Link>
          <div className="sidebar-label">РАБОЧЕЕ ПРОСТРАНСТВО</div>
          <nav aria-label="Главная навигация">
            {links.map(([href, label, num]) => (
              <Link
                key={href}
                href={href}
                className={
                  path === href || path + "/" === href
                    ? "nav-link active"
                    : "nav-link"
                }
                aria-current={
                  path === href || path + "/" === href ? "page" : undefined
                }
              >
                <span>{num}</span>
                {label}
              </Link>
            ))}
          </nav>
          <div className="sidebar-note">
            <span className="tiny-label">ПРИНЦИП РАБОТЫ</span>
            <p>
              Факты и ссылки
              <br />в одном выпуске.
            </p>
            <small>До пяти событий за 24 часа.</small>
          </div>
          <div className="api-status" title="Состояние сервиса">
            <span className={health ? "status-dot" : "status-dot offline"} />
            {health
              ? serverModeLabel(health)
              : healthError
                ? "Нет соединения"
                : "Подключаемся…"}
            <small>Состояние сервиса</small>
            {health && <small>Подробности в выпуске</small>}
          </div>
        </aside>
        <div className="main-area">
          <header className="topbar">
            <span>
              Информационная безопасность <span className="slash">/</span>{" "}
              <strong>
                {links.find(
                  ([href]) => path === href || path + "/" === href,
                )?.[1] || "Рабочее пространство"}
              </strong>
            </span>
            <span className="timezone">
              {health ? "" : healthError ? "Нет соединения · " : ""}
              UTC+3 · Москва
            </span>
          </header>
          {health && path !== "/" && (
            <div className="server-caption">
              <strong>{serverModeLabel(health)}</strong>
              <span>
                Модель сервера: {health.model_name} · промпт:{" "}
                {health.prompt_version}. Режим конкретного выпуска указан в его
                паспорте.
              </span>
            </div>
          )}
          <main id="content" tabIndex={-1}>
            {children}
          </main>
          <footer>
            Кибердайджест <span>Обзор новостей по кибербезопасности.</span>
          </footer>
        </div>
      </div>
    </Context.Provider>
  );
}
export function PageHeading({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow: string;
  title: string;
  description: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="page-heading">
      <div>
        <div className="eyebrow">{eyebrow}</div>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {action}
    </div>
  );
}
export function EmptyResult() {
  const { ready } = useWorkspace();
  return (
    <div className="panel empty-state">
      <div className="empty-mark" aria-hidden="true">
        ↗
      </div>
      <h2>
        {ready
          ? "Здесь появится ваш результат"
          : "Загрузка сохранённого результата…"}
      </h2>
      <p>
        Создайте дайджест или обработайте демонстрационный набор. Результат
        сохраняется в текущей сессии браузера.
      </p>
      <Link href="/create/" className="button primary">
        Создать дайджест →
      </Link>
    </div>
  );
}
export function Alert({
  children,
  kind = "error",
}: {
  children: React.ReactNode;
  kind?: "error" | "warning" | "success";
}) {
  return (
    <div
      className={`alert ${kind}`}
      role={kind === "error" ? "alert" : "status"}
    >
      {children}
    </div>
  );
}
export function MetricGrid({ metrics }: { metrics: Record<string, unknown> }) {
  const items = [
    ["input_count", "Входных материалов"],
    ["relevant_count", "Релевантных"],
    ["excluded_count", "Исключено"],
    ["event_groups", "Групп событий"],
    ["selected_count", "В дайджесте"],
  ];
  return (
    <div className="metrics-grid">
      {items.map(([key, label]) => (
        <div className="metric" key={key}>
          <strong>
            {typeof metrics[key] === "number" ? String(metrics[key]) : "—"}
          </strong>
          <span>{label}</span>
        </div>
      ))}
    </div>
  );
}
