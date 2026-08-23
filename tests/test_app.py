import app as commercia


def test_home_page_loads():
    client = commercia.app.test_client()
    response = client.get("/")
    assert response.status_code == 200
    assert b"Commercia" in response.data


def test_health_reports_missing_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    response = commercia.app.test_client().get("/health")
    assert response.status_code == 200
    assert response.get_json() == {"ok": True, "ai_configured": False}


def test_generate_requires_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    response = commercia.app.test_client().post("/api/generate", json={})
    assert response.status_code == 400
    assert "OPENAI_API_KEY" in response.get_json()["error"]


def test_generate_rejects_invalid_json(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    response = commercia.app.test_client().post(
        "/api/generate", data="not-json", content_type="application/json"
    )
    assert response.status_code == 400
    assert response.get_json()["error"] == "Requête JSON invalide."


def test_home_page_has_manual_instagram_validation():
    response = commercia.app.test_client().get("/")
    assert response.status_code == 200
    assert b"Validation avant Instagram" in response.data
    assert b"downloadCampaign" in response.data
    assert b"approveCampaign" in response.data


def test_automation_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("AUTO_PUBLISH_ENABLED", raising=False)
    response = commercia.app.test_client().get("/api/automation/status")
    assert response.status_code == 200
    assert response.get_json()["enabled"] is False
    assert response.get_json()["mode"] == "automatic"
