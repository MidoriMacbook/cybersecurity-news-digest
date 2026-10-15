import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "contest_validation", ROOT / "scripts/validate_contest.py"
)
assert SPEC is not None and SPEC.loader is not None
validation = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = validation
SPEC.loader.exec_module(validation)


def test_manifest_has_eighteen_distinct_required_scenarios():
    scenarios = validation.scenarios()
    assert len(scenarios) == 18
    assert [scenario.label for scenario in scenarios] == validation.REQUIRED_LABELS
    assert len({scenario.name for scenario in scenarios}) == 18
    assert {s.name for s in scenarios if s.simulation} == {"model_error", "invalid_model"}


def test_failed_expectation_cannot_be_reported_as_pass():
    scenario = validation.scenarios()[0]
    checks = validation.evaluate(scenario, 200, {"events": [], "checks": []})
    assert checks and not all(check["passed"] for check in checks)
    assert all({"expected", "actual", "passed"} <= check.keys() for check in checks)


def test_exception_is_failed_and_saved_without_exception_contents(tmp_path):
    def broken_request(*args, **kwargs):
        raise RuntimeError("private-value-must-never-be-saved")

    record = validation.execute(validation.scenarios()[0], broken_request, tmp_path)
    assert not record["passed"]
    assert record["error_type"] == "RuntimeError"
    serialized = "".join(p.read_text(encoding="utf-8") for p in tmp_path.rglob("*.json"))
    assert "private-value-must-never-be-saved" not in serialized
    folder = tmp_path / "duplicate"
    assert all(
        (folder / name).exists()
        for name in ["input.json", "response.json", "result.json", "verdict.json"]
    )


def test_response_scrubber_removes_secrets(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "private-test-value")
    safe = validation.scrub(
        {
            "authorization": "private-test-value",
            "message": "private-test-value",
            "nested": {"api_key": "anything"},
        }
    )
    assert "private-test-value" not in json.dumps(safe)
    assert safe["nested"]["api_key"] == "[redacted]"


def test_length_verdict_requires_nontrivial_output():
    scenario = next(s for s in validation.scenarios() if s.name == "digest_length")
    checks = validation.evaluate(
        scenario, 200, {"events": [], "checks": [], "digest_text": "", "post_text": ""}
    )
    assert not all(check["passed"] for check in checks)


def test_expanded_synthetic_files_preserve_originals():
    fixtures = ROOT / "data/validation"
    records = json.loads((fixtures / "expanded.json").read_text(encoding="utf-8"))
    assert len(records) >= 8
    assert len({r.get("id") for r in records}) < len(records)
    assert any("<p>" in (r.get("text") or "") for r in records)
    assert any("\n" in (r.get("text") or "") for r in records)
    assert any(len(r.get("text") or "") > 5000 for r in records)
    assert any(r.get("published_at", "").endswith("+03:00") for r in records)
    assert any(r.get("published_at") == "2026-10-14T12:00:00" for r in records)
    assert (fixtures / "expanded.csv").read_text(encoding="utf-8-sig")


@pytest.mark.parametrize("name", ["model_error", "invalid_model"])
def test_simulated_provider_failure_completes_real_api_flow(name):
    scenario = next(case for case in validation.scenarios() if case.name == name)
    status, result = validation.local_request(scenario)
    assert status == 200
    assert result["mode"] == "fallback"
    assert result["llm_attempts"] == 2
    assert len(result["events"]) == 1
    assert all(check["passed"] for check in validation.evaluate(scenario, status, result))
