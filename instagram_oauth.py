import os
import secrets
from datetime import datetime, timedelta, timezone

import requests
from cryptography.fernet import Fernet, InvalidToken
from flask import Blueprint, flash, redirect, request, session, url_for
from flask_login import current_user, login_required

from models import InstagramConnection, db

instagram = Blueprint("instagram", __name__, url_prefix="/instagram")

AUTH_URL = "https://www.instagram.com/oauth/authorize"
TOKEN_URL = "https://api.instagram.com/oauth/access_token"
LONG_LIVED_TOKEN_URL = "https://graph.instagram.com/access_token"
SCOPES = "instagram_business_basic,instagram_business_content_publish"


def connection_health(connection):
    """Verify a stored Instagram connection against the official API."""
    if not connection:
        return {"status": "fail", "code": "not_connected", "message": "Aucun compte Instagram connecté."}
    now = datetime.now(timezone.utc)
    expires_at = connection.token_expires_at
    if expires_at and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at and expires_at <= now:
        return {"status": "fail", "code": "token_expired", "message": "La connexion Instagram a expiré. Reconnectez le compte."}
    try:
        response = requests.get(
            f"https://graph.instagram.com/{os.getenv('META_GRAPH_VERSION', 'v26.0')}/me",
            params={
                "fields": "id,username,account_type,media_count",
                "access_token": decrypt_token(connection.token_ciphertext),
            },
            timeout=20,
        )
        payload = response.json()
        if not response.ok or payload.get("error"):
            error = payload.get("error", {})
            return {
                "status": "fail",
                "code": "api_rejected",
                "message": error.get("message", "Instagram refuse actuellement cette connexion."),
            }
    except (requests.RequestException, ValueError, RuntimeError):
        return {"status": "fail", "code": "api_unreachable", "message": "Impossible de vérifier Instagram pour le moment."}
    days_remaining = None
    status = "pass"
    message = "Compte Instagram opérationnel."
    if expires_at:
        days_remaining = max(0, (expires_at - now).days)
        if days_remaining <= 7:
            status = "warning"
            message = "La connexion Instagram expire bientôt."
    return {
        "status": status,
        "code": "connected",
        "message": message,
        "username": payload.get("username") or connection.username,
        "account_type": payload.get("account_type", ""),
        "media_count": payload.get("media_count"),
        "days_remaining": days_remaining,
    }


def _fernet():
    key = os.getenv("TOKEN_ENCRYPTION_KEY")
    if not key:
        raise RuntimeError("TOKEN_ENCRYPTION_KEY manquante")
    return Fernet(key.encode())


def encrypt_token(token):
    return _fernet().encrypt(token.encode()).decode()


def decrypt_token(ciphertext):
    try:
        return _fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken as error:
        raise RuntimeError("Jeton Instagram illisible") from error


def instagram_ready():
    return all(os.getenv(key) for key in ["META_APP_ID", "META_APP_SECRET", "TOKEN_ENCRYPTION_KEY"])


def _exchange_code(code, callback_url):
    token_response = requests.post(
        TOKEN_URL,
        data={
            "client_id": os.environ["META_APP_ID"],
            "client_secret": os.environ["META_APP_SECRET"],
            "grant_type": "authorization_code",
            "redirect_uri": callback_url,
            "code": code.replace("#_", ""),
        },
        timeout=20,
    )
    token_response.raise_for_status()
    token_data = token_response.json()
    short_token = token_data["access_token"]
    long_response = requests.get(
        LONG_LIVED_TOKEN_URL,
        params={
            "grant_type": "ig_exchange_token",
            "client_secret": os.environ["META_APP_SECRET"],
            "access_token": short_token,
        },
        timeout=20,
    )
    long_response.raise_for_status()
    long_data = long_response.json()
    return token_data, long_data.get("access_token", short_token), int(long_data.get("expires_in", 60 * 24 * 60 * 60))


@instagram.get("/connect")
@login_required
def connect():
    if not instagram_ready():
        flash("La connexion Instagram est en cours de configuration.", "error")
        return redirect(url_for("workspace"))
    state = secrets.token_urlsafe(32)
    session["instagram_oauth_state"] = state
    callback = url_for("instagram.callback", _external=True)
    params = {
        "enable_fb_login": "0",
        "force_authentication": "1",
        "client_id": os.environ["META_APP_ID"],
        "redirect_uri": callback,
        "response_type": "code",
        "scope": SCOPES,
        "state": state,
    }
    prepared = requests.Request("GET", AUTH_URL, params=params).prepare()
    return redirect(prepared.url)


@instagram.get("/callback")
@login_required
def callback():
    expected_state = session.pop("instagram_oauth_state", None)
    if not expected_state or not secrets.compare_digest(expected_state, request.args.get("state", "")):
        flash("La connexion Instagram a expiré. Recommencez depuis votre espace.", "error")
        return redirect(url_for("workspace"))
    if request.args.get("error"):
        flash("Instagram n’a pas autorisé la connexion.", "error")
        return redirect(url_for("workspace"))

    callback_url = url_for("instagram.callback", _external=True)
    try:
        token_data, token, expires_in = _exchange_code(request.args.get("code", ""), callback_url)
    except (requests.RequestException, KeyError, ValueError, RuntimeError):
        flash("Instagram n’a pas pu terminer la connexion. Réessayez dans quelques instants.", "error")
        return redirect(url_for("workspace"))

    connection = current_user.brand.instagram_connection or InstagramConnection(brand=current_user.brand)
    connection.instagram_user_id = str(token_data.get("user_id", ""))
    connection.username = current_user.brand.instagram_handle.lstrip("@")
    connection.token_ciphertext = encrypt_token(token)
    connection.token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
    db.session.add(connection)
    db.session.commit()
    flash("Instagram est maintenant connecté à votre espace.", "success")
    return redirect(url_for("workspace"))


@instagram.post("/disconnect")
@login_required
def disconnect():
    connection = current_user.brand.instagram_connection
    if connection:
        db.session.delete(connection)
        current_user.brand.autopilot_enabled = False
        db.session.commit()
    flash("Le compte Instagram a été déconnecté.", "success")
    return redirect(url_for("workspace"))
