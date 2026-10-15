from app.main import create_app
from app.providers.sources import public_addresses
from app.providers.storage import Storage
from fastapi.testclient import TestClient


def client(tmp_path):
    return TestClient(create_app(Storage(f"sqlite:///{tmp_path / 'test.db'}")))


def test_demo_export_idempotency_and_validation(tmp_path):
    api = client(tmp_path)
    assert api.get("/health").json()["status"] == "ok"
    demo = api.get("/api/v1/demo").json()
    body = {**demo, "use_ai": False}
    first = api.post("/api/v1/digest", json=body, headers={"Idempotency-Key": "test"})
    assert first.status_code == 200, first.text
    result = first.json()
    assert result["event_count"] == 5
    assert all(c["passed"] for c in result["checks"])
    assert (
        api.post("/api/v1/digest", json=body, headers={"Idempotency-Key": "test"}).json()[
            "digest_id"
        ]
        == result["digest_id"]
    )
    body["event_limit"] = 1
    assert (
        api.post("/api/v1/digest", json=body, headers={"Idempotency-Key": "test"}).status_code
        == 409
    )
    ident = result["digest_id"]
    assert api.get(f"/api/v1/digest/{ident}").json() == result
    assert api.get(f"/api/v1/digest/{ident}/export/json").status_code == 200
    assert api.get(f"/api/v1/digest/{ident}/export/csv").status_code == 200
    assert api.post("/api/v1/validate", json=result).json()["valid"]
    assert api.get(f"/api/v1/digest/{ident}/journal?status=excluded_unknown_date").json()


def test_parsing_and_missing_fields(tmp_path):
    api = client(tmp_path)
    for fmt, content in [
        ("json", '[{"title":"тест"}]'),
        ("csv", "title,text\nтест,текст"),
        ("text", "Текст без метаданных"),
    ]:
        response = api.post("/api/v1/parse", json={"format": fmt, "content": content})
        assert response.status_code == 200
        assert response.json()["articles"][0]["published_at"] is None
    assert api.post("/api/v1/parse", json={"format": "json", "content": "bad"}).status_code == 422
    assert (
        api.post(
            "/api/v1/digest", json={"control_time": "2026-10-14T00:00:00", "articles": []}
        ).status_code
        == 422
    )


def test_ssrf_blocks_private_and_reserved(monkeypatch):
    import socket

    import pytest

    for address in ["127.0.0.1", "10.0.0.1", "169.254.169.254", "::1", "2001:db8::1", "192.0.2.1"]:
        monkeypatch.setattr(
            socket,
            "getaddrinfo",
            lambda *args, a=address, **kwargs: [
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", (a, 443))
            ],
        )
        with pytest.raises(ValueError):
            public_addresses("example.com")


def test_unavailable_preview_does_not_abort(tmp_path):
    api = client(tmp_path)
    response = api.post(
        "/api/v1/sources/preview",
        json={"urls": ["http://127.0.0.1/admin", "https://not-allowed.example/a"]},
    )
    assert response.status_code == 200
    assert len(response.json()["journal"]) == 2
    assert all(j["status"] == "source_unavailable" for j in response.json()["journal"])


def test_csv_formula_escaped(tmp_path):
    from app.services.ingestion import export_csv

    text = export_csv([{"title": "=cmd|' /C calc'!A0", "text": "+1", "source": "\t=SUM(1)"}])
    assert "'=cmd" in text and "'+1" in text and "'\t=SUM" in text


def test_validation_rejects_fabricated_output(tmp_path):
    api = client(tmp_path)
    result = api.post("/api/v1/digest/demo", json={}).json()
    result["events"][0]["evidence"][0]["fragment"] = "Выдуманный факт"
    assert not api.post("/api/v1/validate", json=result).json()["valid"]
    result["digest_text"] = "Придуманное утверждение"
    assert not api.post("/api/v1/validate", json=result).json()["valid"]
    result = api.post("/api/v1/digest/demo", json={}).json()
    result["digest_text"] = result["post_text"] = "Придуманное утверждение"
    assert not api.post("/api/v1/validate", json=result).json()["valid"]


def test_request_size_and_rate_limit(tmp_path):
    api = client(tmp_path)
    assert api.post("/api/v1/parse", content="x" * 2_000_001).status_code == 413
    for _ in range(29):
        assert api.post("/api/v1/digest/demo", json={}).status_code == 200
    assert api.post("/api/v1/digest/demo", json={}).status_code == 429
