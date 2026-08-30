"""Publish due customer posts through Instagram Login's official API."""

import logging
import os
from datetime import datetime, timezone

import requests

from instagram_oauth import decrypt_token
from models import ScheduledPost, db

logger = logging.getLogger(__name__)


def _graph_url(path):
    version = os.getenv("META_GRAPH_VERSION", "v26.0")
    return f"https://graph.instagram.com/{version}/{path.lstrip('/')}"


def _post_form(url, payload):
    response = requests.post(url, data=payload, timeout=60)
    response.raise_for_status()
    result = response.json()
    if result.get("error"):
        raise RuntimeError(result["error"].get("message", "Erreur Instagram"))
    return result


def publish_photo(ig_user_id, access_token, image_url, caption):
    container = _post_form(
        _graph_url(f"{ig_user_id}/media"),
        {"image_url": image_url, "caption": caption, "access_token": access_token},
    )
    creation_id = container.get("id")
    if not creation_id:
        raise RuntimeError("Instagram n'a pas créé le conteneur média.")
    published = _post_form(
        _graph_url(f"{ig_user_id}/media_publish"),
        {"creation_id": creation_id, "access_token": access_token},
    )
    if not published.get("id"):
        raise RuntimeError("Instagram n'a pas confirmé la publication.")
    return published["id"]


def run_due_publications(now=None):
    now = now or datetime.now(timezone.utc)
    due_posts = ScheduledPost.query.filter(
        ScheduledPost.status.in_(["scheduled", "retry"]),
        ScheduledPost.scheduled_at <= now,
        ScheduledPost.attempts < 3,
    ).order_by(ScheduledPost.scheduled_at).limit(50).all()
    results = {"published": 0, "failed": 0, "skipped": 0}
    for post in due_posts:
        if not post.brand.autopilot_enabled:
            post.last_error = "Pilote automatique désactivé"
            results["skipped"] += 1
            db.session.commit()
            continue
        connection = post.brand.instagram_connection
        if not connection:
            post.last_error = "Compte Instagram non connecté"
            results["skipped"] += 1
            continue
        try:
            media_id = publish_photo(
                connection.instagram_user_id,
                decrypt_token(connection.token_ciphertext),
                post.media_url,
                post.caption,
            )
            post.status = "published"
            post.meta_media_id = media_id
            post.published_at = datetime.now(timezone.utc)
            post.last_error = None
            results["published"] += 1
        except Exception as error:
            logger.exception("Publication Instagram échouée pour le post %s", post.id)
            post.attempts += 1
            post.status = "retry" if post.attempts < 3 else "failed"
            post.last_error = str(error)[:1000]
            results["failed"] += 1
        db.session.commit()
    logger.info("Cycle de publication terminé: %s", results)
    return results
