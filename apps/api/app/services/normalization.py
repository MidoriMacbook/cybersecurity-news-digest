from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

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
    if data["text"]:
        soup = BeautifulSoup(data["text"], "html.parser")
        for element in soup(["script", "style"]):
            element.decompose()
        data["text"] = soup.get_text(" ", strip=True)
    return Article.model_validate(data)
