# Commercia AI — version réelle connectée à OpenAI

Cette version appelle réellement l'API OpenAI depuis le serveur.

## Démarrage (Mac / Windows / Linux)

1. Installe Python 3.10+.
2. Ouvre un terminal dans ce dossier.
3. Installe les dépendances :

   pip install -r requirements.txt

4. Copie `.env.example` en `.env`.
5. Dans `.env`, remplace `colle_ta_cle_api_ici` par ta clé API OpenAI.
6. Lance :

   python app.py

7. Ouvre dans ton navigateur :

   http://127.0.0.1:5000

## Sécurité
Ne mets jamais ta clé API dans le HTML ou dans un dépôt Git public.
Le fichier `.env` reste uniquement côté serveur.

## Mise en ligne

Le dépôt contient un fichier `render.yaml` prêt pour Render. Après connexion du
dépôt, renseigne `OPENAI_API_KEY` dans les variables d'environnement du service.
Le serveur démarre avec Gunicorn et Render vérifie automatiquement `/health`.

## Tests

    pip install -r requirements.txt pytest
    pytest -q

GitHub Actions relance ces tests à chaque pull request et à chaque changement
sur `main`.

## Ce que fait la version
- Profil Sur un Plateau prérempli
- Appel réel à OpenAI Responses API
- 3 posts Instagram
- 2 concepts de Reels
- 4 Stories
- calendrier 7 jours
- réponse à un avis Google
- offre commerciale
- affichage instantané dans le dashboard

## Pour passer au SaaS vendable
Il restera à ajouter :
- comptes utilisateurs / connexion
- Stripe
- base de données
- stockage de photos / vidéos
- connexion Meta/Instagram pour publication
- historique des campagnes
- analytics
- RGPD / CGV / politique de confidentialité


## Publication Instagram automatique

Le dépôt contient désormais un moteur de publication Instagram via l'API Meta et
un Cron Job Render quotidien. La publication reste désactivée tant que
`AUTO_PUBLISH_ENABLED` n'est pas réglé sur `true`.

Variables nécessaires :

- `META_IG_USER_ID`
- `META_ACCESS_TOKEN`
- `INSTAGRAM_PHOTO_URLS` (URLs publiques séparées par des virgules)
- `AUTO_PUBLISH_ENABLED=true` seulement après un test contrôlé

Le compte Instagram professionnel doit être relié à une Page Facebook technique.
Le Cron Job est configuré à 17:00 UTC, soit 18:00 en heure d'hiver à Paris.
