"""Run the public API demo and save the result locally, without credentials."""

import argparse
import json
from pathlib import Path
from urllib.request import Request, urlopen


def main() -> None:
    parser = argparse.ArgumentParser(description="Запустить синтетический демо-набор")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--output", default="artifacts/demo-result.json")
    args = parser.parse_args()
    request = Request(
        args.base_url.rstrip("/") + "/api/v1/digest/demo",
        data=b"{}",
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=120) as response:
        result = json.load(response)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(result["digest_text"])
    print(f"\nРезультат сохранён: {output.resolve()}")


if __name__ == "__main__":
    main()
