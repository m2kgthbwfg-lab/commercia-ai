from datetime import datetime, timedelta, timezone
from io import BytesIO

import app as commercia
from instagram_publisher import instagram_image_url, run_due_publications, wait_for_container
from models import BrandProfile, Campaign, MediaAsset, ScheduledPost, User, db


def client():
    commercia.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    return commercia.app.test_client()


def create_user(onboarded=True):
    with commercia.app.app_context():
        db.drop_all()
        db.create_all()
        user = User(
            email="client@example.com",
            first_name="Malek",
            password_hash="unused",
            onboarding_complete=onboarded,
            trial_ends_at=datetime.now(timezone.utc) + timedelta(days=7),
        )
        user.brand = BrandProfile(
            business_name="Sur un Plateau",
            activity="Plateaux de fruits",
            location="Paris",
            audience="Particuliers et entreprises",
            description="Créateur de plateaux de fruits",
            differentiators="Produits frais et présentation sur mesure",
            products="Plateaux de fruits frais",
            communication_goals="Obtenir plus de commandes",
        )
        db.session.add(user)
        db.session.commit()
        return user.id


def login_test_client(test_client, user_id):
    with test_client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True


def test_home_page_loads():
    response = client().get("/")
    assert response.status_code == 200
    assert b"Commercia" in response.data
    assert b"r\xc3\xa9seaux sociaux avancent" in response.data
    assert b"Cr\xc3\xa9ateurs, ind\xc3\xa9pendants, marques, entreprises et organisations" in response.data
    assert b"commerces locaux" not in response.data
    assert b"7 jours" in response.data


def test_private_app_requires_login():
    response = client().get("/app")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_workspace_is_personalized():
    user_id = create_user()
    test_client = client()
    login_test_client(test_client, user_id)
    response = test_client.get("/workspace")
    assert response.status_code == 200
    assert b"Bonjour Malek" in response.data
    assert b"Sur un Plateau" in response.data


def test_health_reports_configuration(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    monkeypatch.delenv("META_APP_ID", raising=False)
    monkeypatch.delenv("META_APP_SECRET", raising=False)
    monkeypatch.delenv("SCHEDULER_ENABLED", raising=False)
    response = client().get("/health")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["status"] == "healthy"
    assert payload["checks"] == {
        "ai": "warning",
        "billing": "warning",
        "database": "pass",
        "instagram_oauth": "warning",
        "scheduler": "warning",
    }
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"


def test_scheduler_endpoint_requires_private_token(monkeypatch):
    monkeypatch.setenv("SCHEDULER_TOKEN", "private-test-token")
    response = client().post("/internal/scheduler/run")
    assert response.status_code == 401


def test_scheduler_endpoint_runs_with_private_token(monkeypatch):
    monkeypatch.setenv("SCHEDULER_TOKEN", "private-test-token")
    monkeypatch.setattr(commercia, "run_due_publications", lambda: {"published": 1})
    response = client().post(
        "/internal/scheduler/run",
        headers={"Authorization": "Bearer private-test-token"},
    )
    assert response.status_code == 200
    assert response.get_json() == {"ok": True, "result": {"published": 1}}


def test_generate_requires_login(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    response = client().post("/api/generate", json={})
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_generate_requires_api_key(monkeypatch):
    user_id = create_user()
    test_client = client()
    login_test_client(test_client, user_id)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    response = test_client.post("/api/generate", json={})
    assert response.status_code == 400
    assert "OPENAI_API_KEY" in response.get_json()["error"]


def test_onboarding_pages_and_redirect():
    user_id = create_user(onboarded=False)
    test_client = client()
    login_test_client(test_client, user_id)
    assert test_client.get("/onboarding").status_code == 200
    workspace = test_client.get("/workspace")
    assert workspace.status_code == 302
    assert "/onboarding" in workspace.headers["Location"]


def test_auth_pages_load():
    test_client = client()
    assert test_client.get("/signup").status_code == 200
    assert test_client.get("/login").status_code == 200


def test_signup_and_onboarding_flow():
    with commercia.app.app_context():
        db.drop_all()
        db.create_all()
    test_client = client()
    signup = test_client.post(
        "/signup?plan=pro",
        data={
            "first_name": "Malek",
            "business_name": "Sur un Plateau",
            "activity": "Plateaux de fruits",
            "email": "malek@example.com",
            "password": "motdepasse1",
            "plan": "pro",
        },
    )
    assert signup.status_code == 302
    assert "/onboarding" in signup.headers["Location"]
    onboarding = test_client.post(
        "/onboarding",
        data={
            "business_name": "Commercia AI",
            "activity": "Assistant de communication Instagram",
            "location": "Paris & Ile-de-France",
            "audience": "Particuliers et entreprises",
            "description": "Créateur de plateaux de fruits sur mesure",
            "differentiators": "Fraîcheur et présentation artisanale",
            "products": "Plateaux, corbeilles et événements",
            "communication_goals": "Obtenir plus de commandes",
            "tone": "premium, chaleureux et humain",
            "visual_style": "naturel et coloré",
            "preferred_formats": "Reel, Story, Carrousel, Post",
            "automation_mode": "autopilot",
            "publish_hour": "18:00",
        },
    )
    assert onboarding.status_code == 302
    assert "/workspace" in onboarding.headers["Location"]
    workspace = test_client.get("/workspace")
    assert workspace.status_code == 200
    assert b"Formule Pro" in workspace.data
    assert b"Commercia AI" in workspace.data
    with commercia.app.app_context():
        brand = BrandProfile.query.one()
        assert brand.business_name == "Commercia AI"
        assert brand.activity == "Assistant de communication Instagram"


def test_automation_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("AUTO_PUBLISH_ENABLED", raising=False)
    user_id = create_user()
    test_client = client()
    login_test_client(test_client, user_id)
    response = test_client.get("/api/automation/status")
    assert response.status_code == 200
    assert response.get_json()["enabled"] is False
    assert response.get_json()["mode"] == "automatic"
    assert response.get_json()["connected"] is False


def test_automation_status_requires_login():
    response = client().get("/api/automation/status")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_instagram_health_requires_login():
    response = client().get("/api/instagram/health")
    assert response.status_code == 302


def test_instagram_health_reports_missing_connection():
    user_id = create_user()
    test_client = client()
    login_test_client(test_client, user_id)
    response = test_client.get("/api/instagram/health")
    assert response.status_code == 200
    assert response.get_json()["status"] == "fail"
    assert response.get_json()["code"] == "not_connected"


def test_calendar_requires_login():
    assert client().get("/api/calendar").status_code == 302


def test_calendar_is_empty_for_a_new_brand():
    user_id = create_user()
    test_client = client()
    login_test_client(test_client, user_id)
    response = test_client.get("/api/calendar")
    assert response.status_code == 200
    assert response.get_json() == {"posts": []}


def test_batch_publish_requires_explicit_confirmation():
    user_id = create_user()
    test_client = client()
    login_test_client(test_client, user_id)
    response = test_client.post("/api/instagram/publish-batch", json={"items": []})
    assert response.status_code == 400
    assert "Confirmez" in response.get_json()["error"]


def test_automation_cannot_be_enabled_without_scheduler(monkeypatch):
    monkeypatch.delenv("SCHEDULER_ENABLED", raising=False)
    user_id = create_user()
    test_client = client()
    login_test_client(test_client, user_id)
    response = test_client.post("/api/automation/toggle", json={"enabled": True})
    assert response.status_code == 503
    assert "programmation serveur" in response.get_json()["error"]


def test_automation_cannot_be_enabled_without_instagram(monkeypatch):
    monkeypatch.setenv("SCHEDULER_ENABLED", "true")
    user_id = create_user()
    test_client = client()
    login_test_client(test_client, user_id)
    response = test_client.post("/api/automation/toggle", json={"enabled": True})
    assert response.status_code == 409
    assert "Instagram" in response.get_json()["error"]


def test_publisher_skips_posts_while_autopilot_is_disabled():
    user_id = create_user()
    with commercia.app.app_context():
        user = db.session.get(User, user_id)
        post = ScheduledPost(
            brand_id=user.brand.id,
            caption="Publication de test",
            media_url="https://example.com/photo.jpg",
            scheduled_at=datetime.now(timezone.utc) - timedelta(minutes=1),
            status="scheduled",
        )
        db.session.add(post)
        db.session.commit()
        result = run_due_publications()
        assert result["skipped"] == 1
        assert db.session.get(ScheduledPost, post.id).status == "scheduled"


def test_instagram_image_is_recropped_to_supported_square():
    original = "https://res.cloudinary.com/demo/image/upload/v1/commercia/photo.png"
    transformed = instagram_image_url(original)
    assert "/image/upload/c_pad,b_white,h_1080,w_1080,f_jpg,q_auto/" in transformed


def test_non_cloudinary_image_url_is_unchanged():
    original = "https://example.com/photo.jpg"
    assert instagram_image_url(original) == original


def test_instagram_container_waits_until_finished(monkeypatch):
    class Response:
        ok = True

        def __init__(self, status):
            self.status = status

        def json(self):
            return {"status_code": self.status}

    responses = iter([Response("IN_PROGRESS"), Response("FINISHED")])
    monkeypatch.setattr("instagram_publisher.requests.get", lambda *args, **kwargs: next(responses))
    monkeypatch.setattr("instagram_publisher.time.sleep", lambda *_: None)
    assert wait_for_container("container-id", "token", attempts=2) is None


def test_campaign_requires_real_media_before_scheduling():
    user_id = create_user()
    with commercia.app.app_context():
        user = db.session.get(User, user_id)
        campaign = Campaign(
            brand_id=user.brand.id,
            brief_json={},
            result_json={"posts": [{"caption": "Bonjour", "hashtags": ["#paris"]}]},
        )
        db.session.add(campaign)
        db.session.commit()
        campaign_id = campaign.id
    test_client = client()
    login_test_client(test_client, user_id)
    response = test_client.post(f"/api/campaigns/{campaign_id}/approve")
    assert response.status_code == 409
    assert "photo" in response.get_json()["error"]


def test_media_upload_requires_storage_configuration(monkeypatch):
    monkeypatch.delenv("CLOUDINARY_URL", raising=False)
    user_id = create_user()
    test_client = client()
    login_test_client(test_client, user_id)
    response = test_client.post(
        "/api/media",
        data={"file": (BytesIO(b"fake-image"), "photo.jpg")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 503
