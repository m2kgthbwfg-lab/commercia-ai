# Commercia — SaaS de communication pour commerces locaux

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

## Ce que fait la version commerciale

- comptes clients sécurisés et données séparées
- onboarding de marque très détaillé
- génération personnalisée de Posts, Stories, Reels, offres et calendrier
- historique des campagnes en base de données
- essai de 7 jours et quotas par formule
- abonnements Stripe Checkout et portail de facturation
- connexion Instagram Business officielle avec jeton chiffré
- mode validation ou autopilote
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
sans partager les accès entre les commerces. Le job vérifie les publications
toutes les 15 minutes et retente au maximum trois fois en cas d'erreur.
