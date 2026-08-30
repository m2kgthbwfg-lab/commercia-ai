# Commercia AI — Responsable réseaux sociaux IA

Commercia AI est une plateforme universelle de création, planification et publication de contenu social. Cette version est un MVP Instagram : elle appelle réellement OpenAI et l'API officielle Instagram depuis le serveur.

## État réel du produit

Consultez avant toute évolution :

- [AUDIT.md](AUDIT.md) — fonctionnalités réelles, limites, sécurité et production ;
- [ROADMAP.md](ROADMAP.md) — phases de transformation priorisées ;
- [ARCHITECTURE_TARGET.md](ARCHITECTURE_TARGET.md) — architecture cible progressive ;
- [COMPETITIVE_GAP.md](COMPETITIVE_GAP.md) — écarts concurrentiels vérifiés.

Important : la publication Instagram directe fonctionne. L'exécution planifiée de l'Autopilot nécessite encore le déploiement du service cron/worker décrit dans la roadmap.

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
Le Blueprint prévoit Gunicorn et un contrôle `/health`. Le service Render existant doit encore être aligné sur cette configuration, comme indiqué dans l'audit.

## Tests

    pip install -r requirements.txt pytest
    pytest -q

GitHub Actions relance ces tests à chaque pull request et à chaque changement
sur `main`.

## Ce que fait réellement la version actuelle

- comptes clients sécurisés et données séparées
- onboarding de marque universel
- génération personnalisée de Posts, Stories, Reels, offres et calendrier
- historique des campagnes en base de données
- essai de 7 jours et quotas par formule
- abonnements Stripe Checkout et portail de facturation
- connexion Instagram Business officielle avec jeton chiffré
- mode validation et préparation Autopilot ; le scheduler de production reste à déployer
- protection CSRF, limitation de débit et cookies sécurisés

## Variables de production

Obligatoires pour ouvrir les inscriptions :

- `SECRET_KEY`
- `DATABASE_URL` (URL interne PostgreSQL Render)
- `OPENAI_API_KEY`
- `TOKEN_ENCRYPTION_KEY` (clé Fernet)
- `CLOUDINARY_URL` (bibliothèque de photos)

Pour les abonnements :

- `STRIPE_SECRET_KEY`
- `STRIPE_WEBHOOK_SECRET`
- `STRIPE_PRICE_ESSENTIAL`
- `STRIPE_PRICE_AUTOPILOT`
- `STRIPE_PRICE_PRO`

Pour Instagram Login :

- `META_APP_ID`
- `META_APP_SECRET`

URI de redirection Meta :

    https://commercia-ai.onrender.com/instagram/callback


## Publication Instagram automatique

Chaque client connecte son propre compte professionnel via Instagram Login.
Le jeton est chiffré en base et l'autopilote reste désactivé jusqu'à l'accord
explicite du client. Le Cron Job Render exécutera ensuite les publications dues,
sans partager les accès entre les espaces. Le runner sait vérifier les publications
dues et retenter au maximum trois fois. Le cron doit exister dans Render pour que
cette exécution soit réellement automatique.
