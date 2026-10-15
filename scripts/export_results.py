"""Export an existing result through the API."""

import argparse
from pathlib import Path
from urllib.parse import quote
from urllib.request import urlopen


def main() -> None:
    parser = argparse.ArgumentParser(description="Скачать JSON или CSV результата")
    parser.add_argument("digest_id")
    parser.add_argument("--format", choices=["json", "csv"], default="json")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()
    url = (
        args.base_url.rstrip("/")
        + "/api/v1/digest/"
        + quote(args.digest_id, safe="")
        + "/export/"
        + args.format
    )
    with urlopen(url, timeout=60) as response:
        payload = response.read()
    output = Path(args.output or f"artifacts/result.{args.format}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(payload)
    print(f"Выгрузка сохранена: {output.resolve()}")


if __name__ == "__main__":
    main()
