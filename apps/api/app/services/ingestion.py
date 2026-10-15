import csv
import io
import json
from typing import Any

from pydantic import TypeAdapter

from app.schemas.models import Article


def parse_articles(fmt: str, content: str) -> list[Article]:
    data: Any
    if fmt == "json":
        data = json.loads(content)
        if isinstance(data, dict):
            data = data.get("articles", [])
    elif fmt == "csv":
        data = list(csv.DictReader(io.StringIO(content.lstrip("\ufeff"))))
    else:
        # Unstructured text cannot confirm dates, origin, or URL: retain missing metadata.
        data = [{"text": block} for block in content.split("\n---\n") if block.strip()]
    if not isinstance(data, list) or not all(isinstance(row, dict) for row in data):
        raise ValueError("Ожидается список записей")
    fields = set(Article.model_fields) - {"original_record"}
    data = [
        {
            **{
                key: (value or None) if fmt == "csv" else value
                for key, value in row.items()
                if key in fields
            },
            "original_record": row,
        }
        for row in data
    ]
    articles = TypeAdapter(list[Article]).validate_python(data)
    if len(articles) > 100:
        raise ValueError("Максимум 100 материалов")
    return articles


def export_csv(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "id,status\r\n"
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    for row in rows:
        safe = {}
        for key, value in row.items():
            cell = (
                json.dumps(value, ensure_ascii=False)
                if isinstance(value, (list, dict))
                else str("" if value is None else value)
            )
            if cell.lstrip().startswith(("=", "+", "-", "@")) or cell.startswith(
                ("\t", "\r", "\n")
            ):
                cell = "'" + cell
            safe[key] = cell
        writer.writerow(safe)
    return output.getvalue()
