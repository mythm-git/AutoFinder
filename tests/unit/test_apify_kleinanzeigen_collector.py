"""Network-free tests for the Apify Kleinanzeigen collector."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.error import URLError

import pytest

from autofinder.collectors.apify_kleinanzeigen import ApifyKleinanzeigenCollector, UrllibApifyTransport
from autofinder.core.config import ApifyConfig, CollectionConfig, SearchConfig, load_config
from autofinder.core.exceptions import ApifyConfigurationError, ApifyTransportError, CollectorError, ConfigurationError


ROOT = Path(__file__).resolve().parents[2]
SEARCH = SearchConfig("kleinanzeigen", "27449", 50, "https://example.invalid/configured-search")
COLLECTION = CollectionConfig(listings_per_run=5)
APIFY = ApifyConfig("verifiedActor", 120)


class FakeTransport:
    """Queue deterministic responses while retaining all request arguments."""

    def __init__(self, responses: list[Any]) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[str, str, dict[str, Any] | None, float]] = []

    def request(self, method: str, path: str, payload: dict[str, Any] | None, timeout_seconds: float) -> Any:
        """Record a request and return the next predetermined response."""
        self.calls.append((method, path, payload, timeout_seconds))
        return self.responses.pop(0)


def _run(status: str = "SUCCEEDED") -> dict[str, Any]:
    """Return a minimal validated Apify run wrapper."""
    return {"data": {"id": "run-safe-123", "status": status, "defaultDatasetId": "dataset-safe-123"}}


def _fixture_dataset() -> list[dict[str, Any]]:
    """Load sanitized representative raw marketplace evidence."""
    return json.loads((ROOT / "tests" / "fixtures" / "apify_kleinanzeigen_dataset.json").read_text(encoding="utf-8"))


def test_collect_uses_verified_actor_input_schema_and_preserves_raw_data() -> None:
    """The actor receives exactly searchUrl/maxItems and rich raw fields survive."""
    transport = FakeTransport([_run(), _fixture_dataset()])
    result = ApifyKleinanzeigenCollector(SEARCH, COLLECTION, APIFY, transport).collect()
    method, path, payload, timeout = transport.calls[0]
    assert method == "POST"
    assert path.startswith("/acts/verifiedActor/runs?waitForFinish=")
    assert payload == {"searchUrl": SEARCH.search_url, "maxItems": 5}
    assert timeout == 120
    assert result.requested_count == 5
    assert result.received_count == 1
    assert result.listings[0].raw_data["vehicle"]["mileage"] == 155000
    assert result.listings[0].raw_data["extraStructuredAttribute"] == {"sourceField": "preserved"}
    assert transport.calls[1][1] == "/datasets/dataset-safe-123/items?limit=5"


def test_collect_uses_only_configured_latest_listing_limit() -> None:
    """V0.1 makes one bounded request and never seeks replacement listings."""
    transport = FakeTransport([_run(), []])
    result = ApifyKleinanzeigenCollector(SEARCH, COLLECTION, APIFY, transport).collect()
    assert result.requested_count == 5
    assert transport.calls[0][2] == {"searchUrl": SEARCH.search_url, "maxItems": 5}
    assert len(transport.calls) == 2


def test_collect_allows_zero_results(caplog: pytest.LogCaptureFixture) -> None:
    """A valid empty dataset remains visible as a warning, not a fabricated success."""
    transport = FakeTransport([_run(), []])
    result = ApifyKleinanzeigenCollector(SEARCH, COLLECTION, APIFY, transport).collect()
    assert result.received_count == 0
    assert "zero items" in caplog.text


def test_collect_rejects_malformed_dataset() -> None:
    """Non-array dataset payloads fail closed."""
    transport = FakeTransport([_run(), {"not": "a dataset"}])
    with pytest.raises(CollectorError, match="JSON array"):
        ApifyKleinanzeigenCollector(SEARCH, COLLECTION, APIFY, transport).collect()


def test_collect_rejects_failed_actor_status() -> None:
    """Actor failures do not proceed to a dataset request."""
    transport = FakeTransport([_run("FAILED")])
    with pytest.raises(CollectorError, match="without success"):
        ApifyKleinanzeigenCollector(SEARCH, COLLECTION, APIFY, transport).collect()
    assert len(transport.calls) == 1


def test_configuration_requires_apify_settings(tmp_path: Path) -> None:
    """Missing non-secret actor settings fail configuration validation clearly."""
    broken = (ROOT / "config" / "autofinder.yaml").read_text(encoding="utf-8").replace('  actor_id: "rKEiEgI8vfyKcaBUj"\n', "")
    path = tmp_path / "broken.yaml"
    path.write_text(broken, encoding="utf-8")
    with pytest.raises(ConfigurationError, match="actor_id"):
        load_config(path)


def test_missing_token_and_transport_error_do_not_expose_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """Credential failures and HTTP failures redact representative token material."""
    monkeypatch.delenv("APIFY_API_TOKEN", raising=False)
    with pytest.raises(ApifyConfigurationError) as missing:
        ApifyKleinanzeigenCollector(SEARCH, COLLECTION, APIFY)
    assert "super-secret" not in str(missing.value)

    def fail_request(*args: Any, **kwargs: Any) -> Any:
        raise URLError("offline")

    monkeypatch.setattr("autofinder.collectors.apify_kleinanzeigen.urlopen", fail_request)
    with pytest.raises(ApifyTransportError) as failure:
        UrllibApifyTransport("super-secret").request("GET", "/safe", None, 1)
    assert "super-secret" not in str(failure.value)
