
import os, json, hmac
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import cloudinary.uploader
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, Response
from dotenv import load_dotenv
from openai import OpenAI
from flask_login import LoginManager, current_user, login_required
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash, generate_password_hash
from auth import auth
from billing import billing, stripe_ready
from extensions import limiter
from instagram_oauth import connection_health, decrypt_token, instagram, instagram_ready
from instagram_publisher import publish_photo, run_due_publications
from models import Campaign, MediaAsset, ScheduledPost, UsageEvent, User, db
from social_platforms import platform_statuses

load_dotenv()
app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "development-only-change-me")
database_url = os.getenv("DATABASE_URL", "sqlite:///commercia.db")
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
if database_url.startswith("postgresql://"):
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_pre_ping": True,
        "pool_recycle": 240,
        "pool_size": 5,
        "max_overflow": 5,
    }
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.getenv("RENDER") == "true"

if os.getenv("RENDER") == "true" and app.config["SECRET_KEY"] == "development-only-change-me":
    raise RuntimeError("SECRET_KEY must be configured in production")

db.init_app(app)
limiter.init_app(app)
csrf = CSRFProtect(app)
login_manager = LoginManager(app)
login_manager.login_view = "auth.login"
app.register_blueprint(auth)
app.register_blueprint(billing)
app.register_blueprint(instagram)
csrf.exempt(billing)
limiter.exempt(billing)


def scheduler_ready():
    """Return true only when an external scheduler/worker is explicitly deployed."""
    return os.getenv("SCHEDULER_ENABLED", "false").strip().lower() == "true"


@app.after_request
def add_security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    if request.is_secure:
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response


@login_manager.user_loader
def load_user(user_id):
    try:
        return db.session.get(User, int(user_id))
    except OperationalError:
        app.logger.warning("Connexion PostgreSQL périmée pendant le chargement de session; nouvelle tentative")
        db.session.rollback()
        db.engine.dispose()
        try:
            return db.session.get(User, int(user_id))
        except OperationalError:
            db.session.rollback()
            app.logger.exception("PostgreSQL indisponible après nouvelle tentative")
            return None


with app.app_context():
    db.create_all()


@app.post("/internal/account-recovery")
@csrf.exempt
@limiter.limit("3 per hour")
def internal_account_recovery():
    configured_token = os.getenv("ACCOUNT_RECOVERY_TOKEN", "")
    configured_email = os.getenv("ACCOUNT_RECOVERY_EMAIL", "").strip().lower()
    provided_token = request.headers.get("X-Recovery-Token", "")
    if not configured_token or not provided_token or not hmac.compare_digest(configured_token, provided_token):
        return jsonify({"error": "not_found"}), 404

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    if not configured_email or email != configured_email:
        return jsonify({"error": "not_found"}), 404
    if len(password) < 10 or not any(char.isalpha() for char in password) or not any(char.isdigit() for char in password):
        return jsonify({"error": "invalid_password"}), 400

    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({"error": "not_found"}), 404
    user.password_hash = generate_password_hash(password)
    db.session.commit()
    connection = user.brand.instagram_connection if user.brand else None
    return jsonify({
        "ok": True,
        "instagram_connected": bool(connection),
        "instagram_username": connection.username if connection else "",
    })

SYSTEM = """Tu es Commercia AI, un stratège éditorial et social media universel.
Tu adaptes ton intelligence à toute activité, marque, entreprise, organisation ou créateur, quel que soit son secteur.
Tu crées des contenus concrets, crédibles, élégants, non génériques et immédiatement publiables.
Tu écris toujours en français. Tu évites les promesses excessives. Tu adaptes le ton à la marque.
Réponds UNIQUEMENT en JSON valide avec les clés:
summary, posts, reels, stories, calendar, platform_content, review_reply, commercial_offer.
posts = tableau de 3 à 7 objets {title, caption, hashtags, cta}
reels = tableau de 2 objets {title, hook, shots, overlay_text, caption}
stories = tableau de 4 objets {title, content, interaction}
calendar = tableau de 7 objets {day, content_type, topic, goal}
review_reply = chaîne
commercial_offer = objet {headline, body, cta}
platform_content = objet contenant exactement instagram, facebook, linkedin, tiktok, youtube,
pinterest, threads et x. Chaque valeur est un objet {angle, format, copy, cta} réellement adapté
aux usages du réseau ; ne recopie pas le même texte partout.
"""

@app.get("/")
def index():
    return render_template("landing.html")


@app.get("/app")
@login_required
def dashboard():
    return redirect(url_for("workspace"))

@app.get("/workspace")
@login_required
def workspace():
    if not current_user.onboarding_complete:
        return redirect(url_for("onboarding"))
    return render_template("index.html", user=current_user, brand=current_user.brand)


def is_pilot_user(user):
    return user.selected_plan == "pilot"


@app.get("/api/social/status")
@login_required
def social_status():
    return jsonify({"platforms": platform_statuses(current_user.brand), "pilot": is_pilot_user(current_user)})


@app.post("/api/pilot/activate")
@login_required
@limiter.limit("3 per hour")
def activate_commercia_pilot():
    data = request.get_json(silent=True) or {}
    if data.get("confirmation") != "ACTIVER COMMERCIA":
        return jsonify({"error": "Une confirmation explicite est nécessaire."}), 400
    brand = current_user.brand
    brand.business_name = "Commercia AI"
    brand.activity = "Plateforme universelle de création, gestion, programmation et automatisation des réseaux sociaux"
    brand.location = "France · International"
    brand.audience = "Indépendants, créateurs, marques, entreprises, agences et organisations"
    brand.description = "Commercia aide chaque activité à créer, organiser, publier et améliorer sa présence sur les réseaux sociaux."
    brand.values = "Fiabilité, clarté, autonomie, créativité, transparence et contrôle utilisateur"
    brand.differentiators = "Une intelligence de marque qui adapte une stratégie en contenus multi-réseaux et confirme chaque action réelle."
    brand.products = "Assistant IA social media, calendrier éditorial, création multi-format, programmation, analytics et optimisation"
    brand.communication_goals = "Faire connaître Commercia, démontrer le produit avec ses propres réseaux et recruter les premiers utilisateurs pilotes"
    brand.tone = "premium, technologique, humain, précis et rassurant"
    brand.visual_style = "éditorial premium, minimaliste, contraste maîtrisé, sans codes visuels génériques de l'IA"
    brand.preferred_formats = "Carrousel, démonstration produit, Reel, Story, post expertise, étude de cas et coulisses"
    brand.brand_keywords = "assistant social media, intelligence de marque, contenu, calendrier, automatisation, transparence"
    brand.prohibited_topics = "fausses promesses, faux résultats, statistiques inventées, publication non confirmée par une API"
    current_user.selected_plan = "pilot"
    current_user.subscription_status = "internal_pilot"
    current_user.trial_ends_at = datetime.now(timezone.utc) + timedelta(days=3650)
    current_user.onboarding_complete = True
    db.session.add(UsageEvent(user_id=current_user.id, event_type="commercia_pilot_activated"))
    db.session.commit()
    return jsonify({"ok": True, "redirect": url_for("workspace")})


@app.route("/onboarding", methods=["GET", "POST"])
@login_required
def onboarding():
    brand = current_user.brand
    if request.method == "POST":
        required = {
            "business_name": "le nom de votre marque, entreprise ou projet",
            "activity": "votre activité",
            "location": "votre zone",
            "audience": "votre audience",
            "description": "la présentation de votre activité",
            "differentiators": "vos points forts",
            "products": "vos produits ou services",
            "communication_goals": "votre objectif",
        }
        values = {key: request.form.get(key, "").strip() for key in required}
        missing = [label for key, label in required.items() if not values[key]]
        if missing:
            flash("Complétez " + ", ".join(missing) + ".", "error")
        else:
            for key, value in values.items():
                setattr(brand, key, value)
            for key in ["tone", "values", "visual_style", "preferred_formats", "prohibited_topics", "seasonality", "brand_keywords", "website_url", "instagram_handle", "publish_hour"]:
                setattr(brand, key, request.form.get(key, "").strip())
            brand.approval_required = request.form.get("automation_mode") != "autopilot"
            current_user.onboarding_complete = True
            db.session.commit()
            return redirect(url_for("workspace"))
    return render_template("onboarding.html", brand=brand, user=current_user)


@app.get("/pricing")
def pricing():
    return redirect(url_for("index", _anchor="tarifs"))


def legal_identity():
    return {
        "name": os.getenv("LEGAL_NAME", "Commercia AI"),
        "legal_form": os.getenv("LEGAL_FORM", ""),
        "registration": os.getenv("LEGAL_REGISTRATION", ""),
        "address": os.getenv("LEGAL_ADDRESS", ""),
        "email": os.getenv("LEGAL_EMAIL", "contact@commercia-ai.fr"),
        "director": os.getenv("LEGAL_DIRECTOR", ""),
        "host": "Render Services, Inc., 525 Brannan Street, Suite 300, San Francisco, CA 94107, États-Unis",
    }


@app.get("/mentions-legales")
def legal_notice():
    return render_template("legal.html", page="mentions", legal=legal_identity())


@app.get("/confidentialite")
def privacy_policy():
    return render_template("legal.html", page="privacy", legal=legal_identity())


@app.get("/conditions")
def terms_of_service():
    return render_template("legal.html", page="terms", legal=legal_identity())


@app.get("/account")
@login_required
def account_settings():
    return render_template("account.html", user=current_user, brand=current_user.brand)


@app.get("/account/export")
@login_required
def export_account():
    brand = current_user.brand
    payload = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "user": {"email": current_user.email, "first_name": current_user.first_name, "plan": current_user.selected_plan, "subscription_status": current_user.subscription_status},
        "brand": {column.name: getattr(brand, column.name) for column in brand.__table__.columns if column.name not in {"id", "user_id"}},
        "campaigns": [{"created_at": campaign.created_at.isoformat(), "status": campaign.status, "brief": campaign.brief_json, "result": campaign.result_json} for campaign in Campaign.query.filter_by(brand_id=brand.id).order_by(Campaign.created_at).all()],
        "publications": [{"scheduled_at": post.scheduled_at.isoformat(), "published_at": post.published_at.isoformat() if post.published_at else None, "status": post.status, "caption": post.caption, "media_url": post.media_url, "instagram_media_id": post.meta_media_id} for post in ScheduledPost.query.filter_by(brand_id=brand.id).order_by(ScheduledPost.created_at).all()],
    }
    return Response(json.dumps(payload, ensure_ascii=False, indent=2, default=str), mimetype="application/json", headers={"Content-Disposition": "attachment; filename=commercia-export.json"})


@app.post("/account/delete")
@login_required
@limiter.limit("3 per hour")
def delete_account():
    if current_user.subscription_status in {"active", "past_due", "unpaid"}:
        flash("Résiliez d’abord votre abonnement depuis le portail de facturation.", "error")
        return redirect(url_for("account_settings"))
    if request.form.get("confirmation", "").strip() != "SUPPRIMER" or not check_password_hash(current_user.password_hash, request.form.get("password", "")):
        flash("Confirmation ou mot de passe incorrect.", "error")
        return redirect(url_for("account_settings"))
    user = current_user._get_current_object()
    for asset in list(user.brand.media_assets):
        try:
            cloudinary.uploader.destroy(asset.public_id, invalidate=True)
        except Exception:
            app.logger.exception("Suppression Cloudinary impossible pour %s", asset.public_id)
    Campaign.query.filter_by(brand_id=user.brand.id).delete(synchronize_session=False)
    UsageEvent.query.filter_by(user_id=user.id).delete(synchronize_session=False)
    db.session.delete(user)
    db.session.commit()
    flash("Votre compte et ses données ont été supprimés.", "success")
    return redirect(url_for("index"))


@app.get("/health")
def health():
    database_ok = True
    try:
        db.session.execute(text("SELECT 1"))
    except Exception:
        database_ok = False
        db.session.rollback()
        app.logger.exception("Database health check failed")
    checks = {
        "database": "pass" if database_ok else "fail",
        "ai": "pass" if bool(os.getenv("OPENAI_API_KEY")) else "warning",
        "instagram_oauth": "pass" if instagram_ready() else "warning",
        "billing": "pass" if stripe_ready() else "warning",
        "scheduler": "pass" if scheduler_ready() else "warning",
    }
    return jsonify({
        "ok": database_ok,
        "status": "healthy" if database_ok else "unhealthy",
        "checks": checks,
    }), 200 if database_ok else 503


@app.post("/internal/scheduler/run")
@csrf.exempt
@limiter.exempt
def run_scheduler():
    """Run due publications from a trusted server-side cron trigger."""
    expected = os.getenv("SCHEDULER_TOKEN", "")
    supplied = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    if not expected or not supplied or not hmac.compare_digest(expected, supplied):
        return jsonify({"error": "unauthorized"}), 401
    try:
        result = run_due_publications()
    except Exception:
        app.logger.exception("Scheduled publication run failed")
        return jsonify({"ok": False, "error": "scheduler_failed"}), 500
    return jsonify({"ok": True, "result": result})

@app.get("/api/automation/status")
@login_required
def get_automation_status():
    brand = current_user.brand
    connection = brand.instagram_connection
    return jsonify({
        "enabled": bool(brand.autopilot_enabled and scheduler_ready()),
        "requested": bool(brand.autopilot_enabled),
        "scheduler_ready": scheduler_ready(),
        "connected": bool(connection),
        "mode": "automatic",
        "publish_hour": brand.publish_hour,
        "photo_count": len(brand.media_assets),
        "username": connection.username if connection else "",
        "oauth_configured": instagram_ready(),
    })


@app.get("/api/instagram/health")
@login_required
@limiter.limit("12 per minute")
def instagram_health():
    return jsonify(connection_health(current_user.brand.instagram_connection))


@app.post("/api/automation/toggle")
@login_required
def toggle_automation():
    enabled = bool((request.get_json(silent=True) or {}).get("enabled"))
    brand = current_user.brand
    if enabled and not scheduler_ready():
        return jsonify({
            "error": "Le pilote automatique n’est pas encore disponible : le service de programmation serveur doit être activé."
        }), 503
    if enabled and not brand.instagram_connection:
        return jsonify({"error": "Connectez Instagram avant d’activer le pilote automatique."}), 409
    if enabled and not brand.media_assets:
        return jsonify({"error": "Ajoutez au moins une photo avant d’activer le pilote automatique."}), 409
    brand.autopilot_enabled = enabled
    db.session.commit()
    return jsonify({"ok": True, "enabled": enabled})


@app.post("/api/instagram/test-publish")
@login_required
@limiter.limit("3 per hour")
def test_instagram_publish():
    brand = current_user.brand
    connection = brand.instagram_connection
    asset = MediaAsset.query.filter_by(brand_id=brand.id).order_by(MediaAsset.created_at.desc()).first()
    campaign = Campaign.query.filter_by(brand_id=brand.id).order_by(Campaign.created_at.desc()).first()
    posts = campaign.result_json.get("posts", []) if campaign else []
    if not connection:
        return jsonify({"error": "Instagram n’est pas connecté."}), 409
    if not asset:
        return jsonify({"error": "Ajoutez une photo avant le test."}), 409
    if not posts:
        return jsonify({"error": "Préparez une campagne avant le test."}), 409
    post = posts[0]
    hashtags = post.get("hashtags", "")
    if isinstance(hashtags, list):
        hashtags = " ".join(hashtags)
    caption = "\n\n".join(part for part in [post.get("caption", ""), hashtags] if part)
    try:
        media_id = publish_photo(
            connection.instagram_user_id,
            decrypt_token(connection.token_ciphertext),
            asset.secure_url,
            caption,
        )
    except Exception as error:
        app.logger.exception("Échec de la publication Instagram de test")
        return jsonify({"error": f"Instagram a refusé le test : {str(error)[:300]}"}), 502
    now = datetime.now(timezone.utc)
    db.session.add(ScheduledPost(
        brand_id=brand.id,
        caption=caption,
        media_url=asset.secure_url,
        scheduled_at=now,
        status="published",
        meta_media_id=media_id,
        published_at=now,
    ))
    campaign.status = "tested"
    db.session.commit()
    return jsonify({"ok": True, "media_id": media_id})


@app.post("/api/instagram/publish-batch")
@login_required
@limiter.limit("1 per hour")
def publish_instagram_batch():
    """Publish a small, explicitly confirmed launch batch without duplicates."""
    data = request.get_json(silent=True) or {}
    items = data.get("items")
    if data.get("confirmation") != "PUBLIER" or not isinstance(items, list):
        return jsonify({"error": "Confirmez la publication du lot avant de continuer."}), 400
    if not 1 <= len(items) <= 9:
        return jsonify({"error": "Le lot doit contenir entre 1 et 9 publications."}), 400
    connection = current_user.brand.instagram_connection
    if not connection:
        return jsonify({"error": "Instagram doit être reconnecté avant la publication."}), 409

    asset_ids = []
    for item in items:
        try:
            asset_ids.append(int(item.get("asset_id")))
        except (AttributeError, TypeError, ValueError):
            return jsonify({"error": "Un visuel du lot est invalide."}), 400
    assets = MediaAsset.query.filter(
        MediaAsset.brand_id == current_user.brand.id,
        MediaAsset.id.in_(asset_ids),
    ).all()
    assets_by_id = {asset.id: asset for asset in assets}
    if len(assets_by_id) != len(set(asset_ids)):
        return jsonify({"error": "Un visuel est introuvable dans votre bibliothèque."}), 400

    published = []
    for item, asset_id in zip(items, asset_ids):
        caption = str(item.get("caption", "")).strip()
        if not caption:
            return jsonify({"error": "Chaque publication doit contenir un texte."}), 400
        asset = assets_by_id[asset_id]
        duplicate = ScheduledPost.query.filter_by(
            brand_id=current_user.brand.id,
            caption=caption,
            media_url=asset.secure_url,
            status="published",
        ).first()
        if duplicate:
            published.append({"asset_id": asset.id, "media_id": duplicate.meta_media_id, "duplicate": True})
            continue
        try:
            media_id = publish_photo(
                connection.instagram_user_id,
                decrypt_token(connection.token_ciphertext),
                asset.secure_url,
                caption,
            )
        except Exception as error:
            app.logger.exception("Échec pendant la publication du lot Instagram")
            return jsonify({
                "error": "Instagram a interrompu le lot. Les publications déjà envoyées sont conservées.",
                "detail": str(error)[:250],
                "published": published,
            }), 502
        now = datetime.now(timezone.utc)
        db.session.add(ScheduledPost(
            brand_id=current_user.brand.id,
            caption=caption,
            media_url=asset.secure_url,
            scheduled_at=now,
            status="published",
            meta_media_id=media_id,
            published_at=now,
        ))
        db.session.commit()
        published.append({"asset_id": asset.id, "media_id": media_id, "duplicate": False})
    return jsonify({"ok": True, "published": published})


@app.post("/api/generate")
@login_required
@limiter.limit("10 per minute")
def generate():
    if not os.getenv("OPENAI_API_KEY"):
        return jsonify({
            "error": "OPENAI_API_KEY manquante. Ajoute-la dans le fichier .env puis redémarre l'application."
        }), 400

    if not current_user.onboarding_complete:
        return jsonify({"error": "Terminez d’abord la personnalisation de votre activité."}), 409
    trial_ends_at = current_user.trial_ends_at
    if trial_ends_at and trial_ends_at.tzinfo is None:
        trial_ends_at = trial_ends_at.replace(tzinfo=timezone.utc)
    trial_expired = current_user.subscription_status == "trialing" and trial_ends_at < datetime.now(timezone.utc)
    if not is_pilot_user(current_user) and (current_user.subscription_status not in {"active", "trialing"} or trial_expired):
        return jsonify({"error": "Votre essai ou abonnement n’est plus actif."}), 402

    month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    generation_count = UsageEvent.query.filter(
        UsageEvent.user_id == current_user.id,
        UsageEvent.event_type == "campaign_generated",
        UsageEvent.created_at >= month_start,
    ).count()
    monthly_limits = {"essential": 12, "autopilot": 31, "pro": 60, "pilot": 1000}
    limit = 3 if current_user.subscription_status == "trialing" else monthly_limits.get(current_user.selected_plan, 12)
    if generation_count >= limit:
        return jsonify({"error": "Votre quota mensuel est atteint. Passez à la formule supérieure pour continuer."}), 429

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Requête JSON invalide."}), 400
    brand = current_user.brand
    business = data.get("business") or brand.business_name
    activity = data.get("activity") or brand.activity
    location = data.get("location") or brand.location
    positioning = data.get("positioning") or brand.tone
    audience = data.get("audience") or brand.audience
    offer = data.get("offer", "Votre offre, expertise ou actualité principale")
    objective = data.get("objective", "Développer la visibilité, l’engagement et les opportunités grâce aux réseaux sociaux")
    notes = data.get("notes", "")

    prompt = f"""
MARQUE: {business}
ACTIVITÉ: {activity}
ZONE: {location}
POSITIONNEMENT: {positioning}
CIBLE: {audience}
OFFRE À POUSSER: {offer}
OBJECTIF: {objective}
NOTES: {notes}
FORMULE: {current_user.selected_plan}
PRÉSENTATION: {brand.description}
VALEURS: {brand.values}
POINTS FORTS: {brand.differentiators}
PRODUITS ET SERVICES: {brand.products}
STYLE VISUEL: {brand.visual_style}
FORMATS PRÉFÉRÉS: {brand.preferred_formats}
SAISONNALITÉ: {brand.seasonality}
MOTS À PRIVILÉGIER: {brand.brand_keywords}
SUJETS À ÉVITER: {brand.prohibited_topics}

Conçois une campagne social media complète de 7 jours avec une idée centrale cohérente,
puis adapte-la réellement à Instagram, Facebook, LinkedIn, TikTok, YouTube Shorts,
Pinterest, Threads et X dans platform_content.
Crée 3 publications pour la formule essential et 7 publications pour les formules autopilot, pro ou pilot.
Détecte le secteur, le modèle d’activité et le profil de l’utilisateur à partir de ses réponses.
Adapte entièrement la stratégie, les formats et les angles à son audience, ses objectifs, ses offres,
son identité et ses réseaux. Varie expertise, preuve, pédagogie, coulisses, actualité, communauté et
conversion selon ce profil. N’applique jamais une recette propre à un métier si elle n’est pas pertinente.
Évite les stéréotypes sectoriels, les banalités et les promesses vagues.
Les hashtags doivent être crédibles et peu spammy.
"""

    client = OpenAI()
    try:
        response = client.responses.create(
            model=os.getenv("OPENAI_MODEL", "gpt-5.6"),
            input=[
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": prompt}
            ],
            text={"format": {"type": "json_object"}}
        )
        raw = response.output_text
        result = json.loads(raw)
        campaign = Campaign(brand_id=brand.id, brief_json=data, result_json=result)
        db.session.add(campaign)
        db.session.add(UsageEvent(user_id=current_user.id, event_type="campaign_generated"))
        db.session.commit()
        return jsonify({"ok": True, "result": result, "campaign_id": campaign.id})
    except json.JSONDecodeError:
        app.logger.exception("La réponse OpenAI n'est pas un JSON valide")
        return jsonify({"error": "L'IA a renvoyé une réponse invalide. Réessaie dans quelques instants."}), 502
    except Exception:
        app.logger.exception("Échec de génération OpenAI")
        return jsonify({"error": "La génération a échoué. Vérifie la clé API et réessaie."}), 502


@app.post("/api/media")
@login_required
@limiter.limit("20 per hour")
def upload_media():
    if not os.getenv("CLOUDINARY_URL"):
        return jsonify({"error": "Le stockage des photos est en cours de configuration."}), 503
    uploaded_file = request.files.get("file")
    if not uploaded_file or not uploaded_file.filename:
        return jsonify({"error": "Choisissez une photo."}), 400
    if uploaded_file.mimetype not in {"image/jpeg", "image/png", "image/webp"}:
        return jsonify({"error": "Format accepté : JPG, PNG ou WebP."}), 400
    try:
        result = cloudinary.uploader.upload(
            uploaded_file,
            folder=f"commercia/brands/{current_user.brand.id}",
            resource_type="image",
            transformation=[{"width": 1440, "height": 1440, "crop": "limit", "quality": "auto", "fetch_format": "auto"}],
        )
        asset = MediaAsset(
            brand_id=current_user.brand.id,
            public_id=result["public_id"],
            secure_url=result["secure_url"],
            original_filename=uploaded_file.filename[:255],
        )
        db.session.add(asset)
        db.session.commit()
        return jsonify({"ok": True, "asset": {"id": asset.id, "url": asset.secure_url}})
    except Exception:
        app.logger.exception("Échec de stockage du média")
        return jsonify({"error": "La photo n’a pas pu être enregistrée."}), 502


@app.post("/api/campaigns/<int:campaign_id>/approve")
@login_required
def approve_campaign(campaign_id):
    campaign = Campaign.query.filter_by(id=campaign_id, brand_id=current_user.brand.id).first_or_404()
    if campaign.status == "scheduled":
        return jsonify({"error": "Cette campagne est déjà programmée."}), 409
    assets = MediaAsset.query.filter_by(brand_id=current_user.brand.id).order_by(MediaAsset.created_at.desc()).all()
    if not assets:
        return jsonify({"error": "Ajoutez au moins une vraie photo avant de programmer la campagne."}), 409
    posts = campaign.result_json.get("posts", [])
    hour, minute = [int(part) for part in current_user.brand.publish_hour.split(":")]
    brand_timezone = ZoneInfo(current_user.brand.timezone)
    start = datetime.now(brand_timezone) + timedelta(days=1)
    scheduled = 0
    for index, post in enumerate(posts):
        scheduled_at = (start + timedelta(days=index)).replace(hour=hour, minute=minute, second=0, microsecond=0).astimezone(timezone.utc)
        hashtags = post.get("hashtags", "")
        if isinstance(hashtags, list):
            hashtags = " ".join(hashtags)
        caption = "\n\n".join(part for part in [post.get("caption", ""), hashtags] if part)
        asset = assets[index % len(assets)]
        already_tested = ScheduledPost.query.filter(
            ScheduledPost.brand_id == current_user.brand.id,
            ScheduledPost.status == "published",
            ScheduledPost.caption == caption,
            ScheduledPost.media_url == asset.secure_url,
            ScheduledPost.published_at >= datetime.now(timezone.utc) - timedelta(days=2),
        ).first()
        if already_tested:
            continue
        db.session.add(ScheduledPost(
            brand_id=current_user.brand.id,
            caption=caption,
            media_url=asset.secure_url,
            scheduled_at=scheduled_at,
            status="scheduled",
        ))
        scheduled += 1
    campaign.status = "scheduled"
    db.session.commit()
    return jsonify({"ok": True, "scheduled": scheduled})


@app.get("/api/campaigns/latest")
@login_required
def latest_campaign():
    campaign = Campaign.query.filter_by(brand_id=current_user.brand.id).order_by(Campaign.created_at.desc()).first()
    if not campaign:
        return jsonify({"campaign": None})
    return jsonify({"campaign_id": campaign.id, "campaign": campaign.result_json, "status": campaign.status})


@app.get("/api/calendar")
@login_required
def publication_calendar():
    posts = ScheduledPost.query.filter_by(brand_id=current_user.brand.id).order_by(
        ScheduledPost.scheduled_at.desc()
    ).limit(60).all()
    return jsonify({"posts": [{
        "id": post.id,
        "content_type": post.content_type,
        "caption": post.caption,
        "media_url": post.media_url,
        "scheduled_at": post.scheduled_at.isoformat(),
        "status": post.status,
        "published_at": post.published_at.isoformat() if post.published_at else None,
        "attempts": post.attempts,
        "last_error": post.last_error,
    } for post in posts]})


@app.post("/api/calendar/<int:post_id>/cancel")
@login_required
def cancel_publication(post_id):
    post = ScheduledPost.query.filter_by(id=post_id, brand_id=current_user.brand.id).first_or_404()
    if post.status not in {"scheduled", "retry"}:
        return jsonify({"error": "Seule une publication en attente peut être annulée."}), 409
    post.status = "cancelled"
    post.last_error = None
    db.session.commit()
    return jsonify({"ok": True, "status": post.status})

if __name__ == "__main__":
    if os.getenv("RENDER") == "true" and os.getenv("FLASK_DEBUG") != "1":
        os.execvp("gunicorn", ["gunicorn", "--bind", f"0.0.0.0:{os.getenv('PORT', '10000')}", "--workers", "2", "--timeout", "120", "app:app"])
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=os.getenv("FLASK_DEBUG") == "1")
