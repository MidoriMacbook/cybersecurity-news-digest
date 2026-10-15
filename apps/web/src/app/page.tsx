"use client";
import Link from "next/link";
import { useWorkspace } from "../components/workspace";
import { serverModeLabel } from "../lib/execution";
export default function Home() {
  const { health } = useWorkspace();
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
          Соберите публикации по кибербезопасности в короткий, проверяемый
          дайджест для руководителей, специалистов ИБ и команд SOC.
        </p>
        <div className="button-row">
          <Link className="button primary" href="/create/">
            Создать дайджест <span>↗</span>
          </Link>
          <Link className="button secondary" href="/create/?demo=1">
            Загрузить демонстрационный набор
          </Link>
        </div>
        <div className="hero-footnote">
          {health
            ? `Сервер подключён · ${serverModeLabel(health)}`
            : "Статус сервера отображается в навигации"}
          <span>Ключ API не нужен для демо</span>
        </div>
        <div className="hero-lines" aria-hidden="true">
          <span />
          <span />
          <span />
          <span />
        </div>
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
