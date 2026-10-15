"""Package project sources and the saved acceptance runs without local secrets."""

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    artifacts = ROOT / "artifacts"
    artifacts.mkdir(exist_ok=True)
    source_files = [
        ROOT / name
        for name in [
            "README.md",
            "LICENSE",
            "pyproject.toml",
            "Dockerfile",
            "docker-compose.yml",
            "render.yaml",
            "Makefile",
            ".gitignore",
            ".gitattributes",
            ".dockerignore",
            ".env.example",
            "data/README.md",
            "apps/api/requirements.txt",
            "apps/api/Dockerfile",
            "apps/api/.env.example",
            "apps/web/package.json",
            "apps/web/pnpm-lock.yaml",
            "apps/web/pnpm-workspace.yaml",
            "apps/web/tsconfig.json",
            "apps/web/next.config.ts",
            "apps/web/next-env.d.ts",
            "apps/web/eslint.config.mjs",
            "apps/web/.env.example",
            "apps/web/.prettierignore",
        ]
    ]
    for directory in [
        "apps/api/app",
        "apps/api/tests",
        "apps/web/src",
        "apps/web/tests",
        "data/demo",
        "docs",
        "scripts",
        ".github",
    ]:
        source_files.extend(
            p for p in (ROOT / directory).rglob("*") if p.is_file() and "__pycache__" not in p.parts
        )
    saved = sorted(p for p in (artifacts / "submission").rglob("*") if p.is_file())
    for filename, files in [
        ("submission.zip", saved),
        ("cyberdigest-project.zip", source_files + saved),
    ]:
        with ZipFile(artifacts / filename, "w", compression=ZIP_DEFLATED) as archive:
            for file in sorted(set(files)):
                if file.is_file() and (
                    not file.name.startswith(".env") or file.name == ".env.example"
                ):
                    archive.write(file, file.relative_to(ROOT))
        print(f"Saved {filename}: {(artifacts / filename).stat().st_size} bytes")


if __name__ == "__main__":
    main()
