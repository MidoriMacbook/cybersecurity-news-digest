from zoneinfo import ZoneInfo

from app.domain.rules import parse_date
from app.schemas.models import Article


def normalize(article: Article) -> Article:
    data = article.model_dump()
    for key in ["id", "title", "source", "url", "published_at"]:
        if isinstance(data[key], str):
            data[key] = data[key].strip() or None
    date = parse_date(article.published_at)
    if date:
        data["published_at"] = date.astimezone(ZoneInfo("Europe/Moscow")).isoformat()
    return Article.model_validate(data)
