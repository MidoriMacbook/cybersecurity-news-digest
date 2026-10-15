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
        <div className="eyebrow">ЕЖЕДНЕВНЫЙ ОБЗОР · EUROPE/MOSCOW</div>
        <h1>
          События дня.
          <br />
          <em>Факты на первом месте.</em>
        </h1>
        <p>
          Короткий обзор кибербезопасности: факты, источники и причины выбора в
          одном выпуске.
        </p>
        <div className="button-row">
          <Link className="button primary" href="/create/">
            Создать дайджест <span>↗</span>
          </Link>
          <Link className="button secondary" href="/create/?demo=1">
            Открыть демо
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
            <dd>до контрольного времени</dd>
          </div>
          <div>
            <dt>до 5 событий</dt>
            <dd>с объяснением выбора</dd>
          </div>
          <div>
            <dt>4000 знаков</dt>
            <dd>дайджест, без учёта URL</dd>
          </div>
          <div>
            <dt>Источники и журнал</dt>
            <dd>для проверки каждого факта</dd>
          </div>
        </dl>
      </div>
      <div className="section-heading">
        <h2>От публикаций к ясной картине</h2>
        <span>ПРОЦЕСС / 03 ЭТАПА</span>
      </div>
      <div className="process-grid">
        <article>
          <span className="process-number">01</span>
          <h3>Соберите материалы</h3>
          <p>
            JSON, CSV, текст или RSS и HTML. Контрольное время определяет
            последние 24 часа.
          </p>
        </article>
        <article>
          <span className="process-number">02</span>
          <h3>Проверьте контекст</h3>
          <p>
            Отбор по периоду и теме, объединение повторов, сохранение оговорок и
            противоречий.
          </p>
        </article>
        <article>
          <span className="process-number">03</span>
          <h3>Подготовьте выпуск</h3>
          <p>
            До пяти событий, письмо и пост. Причины выбора, источники и журнал
            доступны рядом.
          </p>
        </article>
      </div>
      <section className="jury-preview" aria-labelledby="jury-preview-title">
        <div>
          <div className="eyebrow">ЧТО УВИДИТ ЖЮРИ</div>
          <h2 id="jury-preview-title">От события — к подтверждению</h2>
          <p>
            Откройте демо, подготовьте выпуск и сравните дайджест, письмо и
            пост. Во вкладках рядом — источники, причины выбора и журнал.
          </p>
          <Link href="/create/?demo=1" className="text-link">
            Проверить на учебном наборе →
          </Link>
        </div>
        <article className="sample-event" aria-label="Учебный пример события">
          <span className="sample-label">
            УЧЕБНЫЙ ПРИМЕР · СИНТЕТИЧЕСКИЕ ДАННЫЕ
          </span>
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
          <small>
            ID: vulnerability · учебный источник example.org/demo/vulnerability
          </small>
        </article>
      </section>
      <div className="home-bottom">
        <div>
          <div className="eyebrow">ПРОЗРАЧНОСТЬ ПО УМОЛЧАНИЮ</div>
          <h2>
            Не хватает данных?
            <br />
            Это тоже часть результата.
          </h2>
          <p>
            Неизвестные даты и неподтверждённые сведения не превращаются в
            факты. Каждый исключённый материал получает объяснение.
          </p>
        </div>
        <Link href="/docs/" className="text-link">
          Как устроен дайджест →
        </Link>
      </div>
    </>
  );
}
