"""Automatic Instagram publishing for Commercia AI.

The job is disabled unless AUTO_PUBLISH_ENABLED=true. Instagram publishing uses
Meta's container + media_publish flow. Images must be publicly reachable.
"""

import json
import logging
import os
import random
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from openai import OpenAI

logger = logging.getLogger(__name__)


def _enabled():
    return os.getenv("AUTO_PUBLISH_ENABLED", "").lower() == "true"


def automation_status():
    required = {
        "META_IG_USER_ID": bool(os.getenv("META_IG_USER_ID")),
        "META_ACCESS_TOKEN": bool(os.getenv("META_ACCESS_TOKEN")),
    }
    photo_urls = [url.strip() for url in os.getenv("INSTAGRAM_PHOTO_URLS", "").split(",") if url.strip()]
    return {
        "enabled": _enabled(),
        "connected": all(required.values()),
        "configured": required,
        "photo_count": len(photo_urls),
        "publish_hour": os.getenv("PUBLISH_HOUR", "18:00"),
        "timezone": os.getenv("PUBLISH_TIMEZONE", "Europe/Paris"),
        "mode": "automatic",
    }


def _post_form(url, payload):
    encoded = urllib.parse.urlencode(payload).encode()
    request = urllib.request.Request(url, data=encoded, method="POST")
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode())


def _graph_url(path):
    version = os.getenv("META_GRAPH_VERSION", "v23.0")
    return f"https://graph.facebook.com/{version}/{path.lstrip('/')}"


def _generate_caption():
    client = OpenAI()
    business = os.getenv("BUSINESS_NAME", "Commercia AI")
    activity = os.getenv("BUSINESS_ACTIVITY", "commerce de proximité")
    offer = os.getenv("BUSINESS_OFFER", "nos produits et services")
    response = client.responses.create(
        model=os.getenv("OPENAI_MODEL", "gpt-5.6"),
        input=[
            {
                "role": "system",
                "content": (
                    "Tu es un community manager Instagram expert. Écris une légende en français, "
                    "élégante, concrète et immédiatement publiable. Ajoute un appel à l'action et "
                    "5 à 8 hashtags crédibles. Ne renvoie que la légende."
                ),
            },
            {
                "role": "user",
                "content": f"Marque: {business}. Activité: {activity}. Offre à promouvoir: {offer}.",
            },
        ],
    )
    return response.output_text.strip()


def _choose_image():
    urls = [url.strip() for url in os.getenv("INSTAGRAM_PHOTO_URLS", "").split(",") if url.strip()]
    if not urls:
        raise RuntimeError("Aucune photo publique configurée dans INSTAGRAM_PHOTO_URLS.")
    return random.choice(urls)


def publish_photo(image_url, caption):
    ig_user_id = os.environ["META_IG_USER_ID"]
    access_token = os.environ["META_ACCESS_TOKEN"]
    container = _post_form(
        _graph_url(f"{ig_user_id}/media"),
        {"image_url": image_url, "caption": caption, "access_token": access_token},
    )
    creation_id = container.get("id")
    if not creation_id:
        raise RuntimeError(f"Meta n'a pas créé le conteneur: {container}")
    published = _post_form(
        _graph_url(f"{ig_user_id}/media_publish"),
        {"creation_id": creation_id, "access_token": access_token},
    )
    if not published.get("id"):
        raise RuntimeError(f"Meta n'a pas publié le média: {published}")
    return published["id"]


def run_daily_publication():
    if not _enabled():
        logger.info("Publication ignorée: AUTO_PUBLISH_ENABLED n'est pas activé.")
        return {"published": False, "reason": "disabled"}
    status = automation_status()
    if not status["connected"]:
        raise RuntimeError("La connexion Instagram n'est pas complètement configurée.")
    image_url = _choose_image()
    caption = _generate_caption()
    media_id = publish_photo(image_url, caption)
    result = {
        "published": True,
        "media_id": media_id,
        "published_at": datetime.now(timezone.utc).isoformat(),
        "image_url": image_url,
    }
    logger.info("Publication Instagram réussie: %s", media_id)
    return result
