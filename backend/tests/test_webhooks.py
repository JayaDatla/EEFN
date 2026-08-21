import os
import sys
import uuid

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.models import PipelineRun
from app.webhooks import notify_pipeline_run_completed


def _run(status="success", failures=None):
    return PipelineRun(
        id=uuid.uuid4(), status=status, limit_requested=50, targets_processed=48,
        failures=failures or [], catalogs_used=["NASA Exoplanet Archive", "Gaia DR3"],
        duration_seconds=12.5,
    )


def test_webhook_not_sent_when_no_urls_configured(monkeypatch, requests_mock):
    from app.config import settings
    monkeypatch.setattr(settings, "WEBHOOK_URLS", "")

    notify_pipeline_run_completed(_run())
    assert requests_mock.call_count == 0


def test_webhook_sent_with_expected_payload_shape(monkeypatch, requests_mock):
    from app.config import settings
    monkeypatch.setattr(settings, "WEBHOOK_URLS", "https://example.com/hook")
    requests_mock.post("https://example.com/hook", json={"ok": True})

    run = _run(status="partial_failure", failures=[{"target": "TOI-1.01", "error": "boom"}])
    notify_pipeline_run_completed(run)

    assert requests_mock.call_count == 1
    payload = requests_mock.last_request.json()
    assert payload["event"] == "pipeline_run.completed"
    assert payload["status"] == "partial_failure"
    assert "text" in payload  # renders sensibly on a raw Slack incoming webhook
    assert "1" in payload["text"]  # failure count mentioned


def test_webhook_fans_out_to_multiple_configured_urls(monkeypatch, requests_mock):
    from app.config import settings
    monkeypatch.setattr(settings, "WEBHOOK_URLS", "https://a.example.com/hook, https://b.example.com/hook")
    requests_mock.post("https://a.example.com/hook", json={})
    requests_mock.post("https://b.example.com/hook", json={})

    notify_pipeline_run_completed(_run())
    assert requests_mock.call_count == 2


def test_webhook_failure_does_not_raise(monkeypatch, requests_mock):
    """UPGRADE_PLAN.md G.3: a webhook delivery failure must never fail the pipeline
    run itself."""
    from app.config import settings
    monkeypatch.setattr(settings, "WEBHOOK_URLS", "https://example.com/hook")
    requests_mock.post("https://example.com/hook", status_code=500)

    notify_pipeline_run_completed(_run())  # must not raise
