from pathlib import Path

from System_Services.n8n_service import N8NService


class FakeResponse:
    status_code = 200
    text = "ok"

    def raise_for_status(self):
        return None

    def json(self):
        return {"accepted": True}


def test_n8n_service_reports_disabled(monkeypatch):
    monkeypatch.setenv("N8N_ENABLED", "false")

    service = N8NService(Path("."))

    assert service.is_configured() is False
    assert service.status()["enabled"] is False


def test_n8n_status_does_not_expose_secrets(monkeypatch):
    monkeypatch.setenv("N8N_ENABLED", "true")
    monkeypatch.setenv("N8N_API_KEY", "super-secret-api-key")
    monkeypatch.setenv("N8N_WEBHOOK_SECRET", "super-secret-webhook")

    status = N8NService(Path(".")).status()

    assert status["api_key_configured"] is True
    assert status["webhook_secret_configured"] is True
    assert "super-secret-api-key" not in str(status)
    assert "super-secret-webhook" not in str(status)


def test_n8n_call_webhook_uses_mocked_post(monkeypatch):
    captured = {}

    def fake_post(url, json, headers, timeout):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setenv("N8N_ENABLED", "true")
    monkeypatch.setenv("N8N_WEBHOOK_BASE_URL", "http://localhost:5678/webhook")
    monkeypatch.setenv("N8N_API_KEY", "secret-api")
    monkeypatch.setenv("N8N_WEBHOOK_SECRET", "secret-webhook")
    monkeypatch.setenv("N8N_TIMEOUT_SECONDS", "12")
    monkeypatch.setattr("System_Services.n8n_service.requests.post", fake_post)

    result = N8NService(Path(".")).call_webhook("vaila/test", {"hello": "world"})

    assert result["ok"] is True
    assert captured["url"] == "http://localhost:5678/webhook/vaila/test"
    assert captured["json"] == {"hello": "world"}
    assert captured["headers"]["X-N8N-API-Key"] == "secret-api"
    assert captured["headers"]["X-Vaila-Webhook-Secret"] == "secret-webhook"
    assert captured["timeout"] == 12
    assert "secret-api" not in str(result)
    assert "secret-webhook" not in str(result)
