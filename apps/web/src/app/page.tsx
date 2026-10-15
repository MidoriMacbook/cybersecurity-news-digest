"use client";
import Link from "next/link";
import { useWorkspace } from "../components/workspace";
import { presentationStatus } from "../lib/execution";
export default function Home() {
  const { health, healthError } = useWorkspace();
  const status = presentationStatus(health, healthError);
  return (
    <>
      <div className="home-hero">
        <div className="eyebrow">НОВОСТИ КИБЕРБЕЗОПАСНОСТИ</div>
        <h1>
          Главное за день.
          <br />
          <em>С опорой на источники.</em>
        </h1>
        <p>
          Соберите новости в короткий дайджест, письмо и пост со ссылками на
          источники.
        </p>
        <div className="button-row">
          <Link className="button primary" href="/create/">
            Создать выпуск <span>↗</span>
          </Link>
          <Link className="button secondary" href="/create/?demo=1">
            Открыть пример
          </Link>
        </div>
        <section
          className="home-status"
          aria-label="Статус системы"
          role="status"
        >
          <div className="home-status-heading">
            <strong>{status.title}</strong>
            <span>{status.api}</span>
          </div>
          <p>{status.description}</p>
          <div className="home-status-details">
            <span>{status.demo}</span>
            <span>{status.key}</span>
          </div>
          <small>{status.hint}</small>
        </section>
        <dl className="home-limits" aria-label="Формат выпуска">
          <div>
            <dt>24 часа</dt>
            <dd>за выбранный период</dd>
          </div>
          <div>
            <dt>до 5 событий</dt>
            <dd>в одном выпуске</dd>
          </div>
          <div>
            <dt>4000 знаков</dt>
            <dd>без учёта ссылок</dd>
          </div>
          <div>
            <dt>Источники и журнал</dt>
            <dd>рядом с результатом</dd>
          </div>
        </dl>
      </div>
      <div className="section-heading">
        <h2>Как создать выпуск</h2>
        <span>ТРИ ШАГА</span>
      </div>
      <div className="process-grid">
        <article>
          <span className="process-number">01</span>
          <h3>Соберите материалы</h3>
          <p>
            Загрузите файл, вставьте текст или добавьте ссылки на публикации.
          </p>
        </article>
        <article>
          <span className="process-number">02</span>
          <h3>Задайте период</h3>
          <p>
            Укажите дату и время. Сервис выберет новости за предыдущие 24 часа и
            объединит повторы.
          </p>
        </article>
        <article>
          <span className="process-number">03</span>
          <h3>Подготовьте выпуск</h3>
          <p>
            Нажмите «Подготовить выпуск». Дайджест, письмо и пост появятся в
            разделе «Результат».
          </p>
        </article>
      </div>
      <section className="jury-preview" aria-labelledby="jury-preview-title">
        <div>
          <div className="eyebrow">ПРИМЕР ВЫПУСКА</div>
          <h2 id="jury-preview-title">Новость и её источник</h2>
          <p>
            Откройте пример, чтобы посмотреть готовые форматы, источники и
            журнал обработки.
          </p>
          <Link href="/create/?demo=1" className="text-link">
            Попробовать пример →
          </Link>
        </div>
        <article className="sample-event" aria-label="Учебный пример события">
          <span className="sample-label">УЧЕБНЫЙ ПРИМЕР</span>
          <h3>Поставщик выпустил исправление уязвимости</h3>
          <p>
            Учебный поставщик подтвердил уязвимость CVE-2026-10001 в сервере.
            Сведения об эксплуатации отсутствуют.
          </p>
          <div className="sample-evidence">
            <strong>Основание</strong>
            <span>
              «Выпущено исправление; сведения об эксплуатации отсутствуют.»
            </span>
          </div>
          <small>Учебный источник: example.org/demo/vulnerability</small>
        </article>
      </section>
      <div className="home-bottom">
        <div>
          <div className="eyebrow">ПОДРОБНОСТИ ВЫПУСКА</div>
          <h2>
            Каждое решение
            <br />
            можно проверить.
          </h2>
          <p>
            В журнале видно, какие материалы вошли в выпуск и почему. Ссылки
            помогают сверить текст с источниками.
          </p>
        </div>
        <Link href="/docs/" className="text-link">
          Как это работает →
        </Link>
      </div>
    </>
  );
}
