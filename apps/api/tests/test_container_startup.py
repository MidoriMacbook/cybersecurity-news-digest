import runpy
from pathlib import Path, PurePosixPath

from app import main
from fastapi.testclient import TestClient


def test_configured_demo_path_starts_in_shallow_container_layout(monkeypatch):
    demo_dir = Path(main.__file__).resolve().parents[3] / "data/demo"
    original_resolve = Path.resolve

    def container_resolve(path, *args, **kwargs):
        if str(path) == main.__file__:
            return PurePosixPath("/app/app/main.py")
        return original_resolve(path, *args, **kwargs)

    monkeypatch.setenv("DEMO_DATA_DIR", str(demo_dir))
    monkeypatch.setenv("DATABASE_URL", "sqlite://")
    monkeypatch.delenv("STATIC_DIR", raising=False)
    monkeypatch.setattr(Path, "resolve", container_resolve)
    loaded = runpy.run_path(main.__file__)
    api = TestClient(loaded["app"])
    assert api.get("/health").json()["status"] == "ok"
    assert api.get("/api/v1/demo").json()["articles"]
