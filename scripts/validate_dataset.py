"""Validate a JSON/CSV input using the application's Pydantic model."""

import argparse
import csv
import json
import sys
from pathlib import Path

from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "api"))


def main() -> None:
    from app.schemas.input import ArticleInput

    parser = argparse.ArgumentParser(description="Проверить структуру набора JSON/CSV")
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    with args.path.open(encoding="utf-8-sig", newline="") as file:
        records = (
            list(csv.DictReader(file)) if args.path.suffix.lower() == ".csv" else json.load(file)
        )
    if not isinstance(records, list):
        raise SystemExit("Ожидается массив публикаций")
    failures = 0
    for index, record in enumerate(records, start=1):
        try:
            ArticleInput.model_validate(record)
        except ValidationError:
            failures += 1
            print(f"Запись {index}: структура не соответствует схеме")
    print(f"Записей: {len(records)}; структурных ошибок: {failures}")
    print("Период, достаточность текста и факты проверяются при обработке API.")
    raise SystemExit(1 if failures else 0)


if __name__ == "__main__":
    main()
