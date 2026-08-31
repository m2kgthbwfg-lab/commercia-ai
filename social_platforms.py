"""Truthful platform capability catalogue for Commercia."""

PLATFORMS = (
    {"id": "instagram", "name": "Instagram", "formats": "Posts, carrousels, Reels et Stories", "publishing": True},
    {"id": "facebook", "name": "Facebook", "formats": "Publications, vidéos et Pages", "publishing": False},
    {"id": "linkedin", "name": "LinkedIn", "formats": "Posts, documents et expertise", "publishing": False},
    {"id": "tiktok", "name": "TikTok", "formats": "Vidéos courtes et scripts", "publishing": False},
    {"id": "youtube", "name": "YouTube", "formats": "Shorts, titres et descriptions", "publishing": False},
    {"id": "pinterest", "name": "Pinterest", "formats": "Épingles et tableaux", "publishing": False},
    {"id": "threads", "name": "Threads", "formats": "Conversations et séries de posts", "publishing": False},
    {"id": "x", "name": "X", "formats": "Posts courts et fils", "publishing": False},
)


def platform_statuses(brand):
    statuses = []
    for platform in PLATFORMS:
        connected = platform["id"] == "instagram" and bool(brand.instagram_connection)
        item = dict(platform)
        item.update({
            "connected": connected,
            "content_ready": True,
            "status": "connected" if connected else ("ready_to_connect" if platform["publishing"] else "authorization_required"),
            "status_label": "Connecté" if connected else ("Prêt à connecter" if platform["publishing"] else "Accès API à autoriser"),
        })
        statuses.append(item)
    return statuses
