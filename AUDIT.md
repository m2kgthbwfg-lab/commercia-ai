# Audit produit et technique — Commercia AI

Date de référence : 31 août 2026

## Verdict

Commercia est aujourd'hui un **MVP SaaS Instagram fonctionnel**, pas encore un Social Media Manager autonome commercialisable à grande échelle.

Le produit sait réellement :

- créer un compte et isoler les données par utilisateur ;
- construire un profil de marque ;
- générer une campagne Instagram avec OpenAI ;
- importer des images dans Cloudinary ;
- connecter un compte Instagram professionnel par OAuth officiel ;
- publier une image et confirmer l'identifiant retourné par Instagram ;
- enregistrer une campagne et des publications dans PostgreSQL ;
- ouvrir Stripe Checkout et traiter les principaux événements d'abonnement ;
- empêcher l'activation de l'Autopilot sans compte Instagram ni média.

Il ne sait pas encore réellement :

- exécuter l'Autopilot en production de façon planifiée ;
- récupérer des analytics Instagram ;
- apprendre des performances ;
- gérer un calendrier jour/semaine/mois éditable ;
- publier sur plusieurs réseaux ;
- gérer plusieurs marques, organisations ou membres ;
- récupérer un mot de passe ou vérifier une adresse e-mail ;
- produire automatiquement des images ou vidéos dans le parcours client ;
- gérer une inbox sociale ;
- exporter ou supprimer les données d'un compte depuis l'interface.

## Architecture actuelle

| Couche | État réel | Évaluation |
|---|---|---|
| Frontend | Jinja, HTML/CSS/JavaScript directement dans quatre templates | Simple et rapide, mais difficile à faire évoluer vers un dashboard complexe |
| Backend | Monolithe Flask dans `app.py` avec blueprints Auth, Billing et Instagram | Correct pour un MVP, responsabilités déjà trop concentrées |
| Base de données | SQLAlchemy, PostgreSQL sur Render, SQLite en local | Fonctionnel, mais aucune migration versionnée |
| Authentification | Flask-Login, hash Werkzeug, CSRF, rate limiting | Bonne base ; récupération, vérification e-mail et gestion des sessions manquent |
| IA | OpenAI Responses API, un prompt système et un prompt métier | Fonctionnel ; absence de modules spécialisés, schéma strict et contrôle qualité |
| Médias | Cloudinary, images JPEG/PNG/WebP | Fonctionnel ; validation basée surtout sur le MIME déclaré |
| Instagram | OAuth officiel Instagram Business, token chiffré, publication d'images | Parcours vertical réel et testé |
| Facturation | Stripe Checkout, portail et webhook | Base présente ; idempotence webhook et parcours d'abonnement incomplets |
| Planification | `ScheduledPost`, runner et définition cron dans `render.yaml` | Code présent, mais aucun cron/worker Render n'est actuellement déployé |
| Tests | 19 tests Pytest + GitHub Actions | Bon début ; intégrations externes et permissions encore peu couvertes |

## État de la production Render

- Un seul service existe : `commercia-ai`.
- Le service utilise le plan gratuit et une seule instance.
- La commande réelle est `python app.py`, donc le serveur de développement Flask est utilisé en production.
- Aucun health check Render n'est configuré sur le service réel.
- Aucun cron job ou worker de publication n'est déployé.
- `render.yaml` décrit Gunicorn, `/health` et un cron, mais cette configuration n'est pas appliquée au service actuel.
- Les logs confirment plusieurs avertissements Flask : « development server ».
- Les anciens échecs Instagram observés correspondent aux essais précédant la correction du format d'image ; des publications réelles ont ensuite réussi.

Conclusion : le bouton Autopilot peut être activé et les posts peuvent être enregistrés comme programmés, mais aucun processus de production ne vient actuellement les publier à l'heure prévue.

## Modèle de données actuel

Modèles présents :

- `User`
- `BrandProfile`
- `InstagramConnection`
- `ScheduledPost`
- `Campaign`
- `MediaAsset`
- `UsageEvent`

Limites :

- relation directe `User -> BrandProfile` en un-à-un ;
- aucune `Organization`, `Workspace`, `Membership` ou permission ;
- mémoire de marque mélangée dans `BrandProfile` ;
- campagne générée conservée en JSON sans entités de contenu éditables ;
- absence d'analytics, recommandations, décisions, expériences et audit logs ;
- absence d'Alembic/Flask-Migrate ; `db.create_all()` ne permet pas une évolution sûre du schéma.

## Audit par parcours

### Inscription et onboarding

État : **partiellement terminé**.

Points solides : validation serveur, mot de passe hashé, CSRF, profil universel, choix d'autonomie.

Manques : vérification e-mail, récupération de compte, consentements, langue, logo, couleurs structurées, concurrents, réseaux utilisés, règles détaillées, import du site et Brand Brain explicite.

### Génération IA

État : **fonctionnel mais monolithique**.

Points solides : données de marque injectées, quota serveur, résultat persisté, erreur JSON gérée.

Risques : un seul prompt volumineux, aucune validation de schéma métier, aucune étape de stratégie, aucun filtre sectoriel sensible, aucune vérification factuelle, aucun score qualité et génération synchrone bloquante.

### Médias

État : **fonctionnel pour les images**.

Manques : logo et palette structurés, vidéos, métadonnées, tags, droits d'utilisation, suppression, vérification réelle du fichier, gestion des doublons et cycle de rétention.

### Instagram

État : **publication d'image réelle**.

Points solides : OAuth state, jeton chiffré, API officielle, attente du traitement du conteneur, confirmation de l'identifiant publié, prévention partielle des doublons.

Manques : rafraîchissement du token, détection d'expiration, reconnexion guidée, carrousels/Reels/Stories selon capacités API, suppression/annulation, analytics et webhooks de statut.

### Programmation et Autopilot

État : **incomplet en production**.

Le modèle, les statuts et le runner existent. Le service planifié n'existe pas. Les retries sont immédiats à chaque cycle, sans backoff, verrouillage de ligne ni clé d'idempotence externe. Deux workers pourraient publier le même post.

### Analytics et optimisation

État : **absent**.

Aucune donnée de portée, impression, engagement ou évolution d'audience n'est récupérée. Aucune recommandation présentée comme réelle ne doit être ajoutée avant cette collecte.

### Facturation

État : **base fonctionnelle, commercialisation incomplète**.

Stripe Checkout, portail et webhook existent. Il manque notamment l'idempotence des événements, un journal d'événements, les cas de paiement échoué, l'actualisation fiable des plans, les e-mails et les tests d'intégration Stripe.

## Sécurité

### Points positifs

- secrets côté serveur ;
- chiffrement Fernet du token Instagram ;
- protection CSRF ;
- cookies HttpOnly, SameSite Lax et Secure sur Render ;
- rate limiting ;
- contrôle de propriété sur campagnes et médias ;
- signature Stripe vérifiée.

### Priorité critique

1. Remplacer le serveur Flask de développement par Gunicorn.
2. Interdire le secret de session de secours en production.
3. Ajouter des migrations et supprimer `db.create_all()` du démarrage de production.
4. Déployer une exécution planifiée fiable avant de vendre l'Autopilot.
5. Ajouter verrouillage/idempotence à la publication.

### Priorité haute

- stockage distribué du rate limiter au lieu de `memory://` ;
- en-têtes CSP, HSTS, frame protection et politique Referrer ;
- validation réelle des fichiers et suppression sécurisée ;
- expiration/rotation/revocation des tokens ;
- idempotence Stripe ;
- journal d'audit ;
- politique de conservation et suppression/export des données ;
- surveillance structurée des erreurs.

## Performance et exploitation

- génération OpenAI et publication Instagram exécutées dans les requêtes HTTP ;
- `time.sleep()` utilisé pendant le traitement Instagram ;
- aucune file de tâches ;
- pas de cache partagé ;
- rate limits locaux à l'instance ;
- pas de tracing ni outil de suivi d'erreurs ;
- service gratuit susceptible de se mettre en veille ;
- dépendances définies uniquement avec des bornes minimales, donc builds non reproductibles.

## Dépendances

Les bibliothèques installées localement sont récentes au moment de l'audit. Le problème principal n'est pas une version manifestement obsolète, mais l'absence de verrouillage : `Flask>=3.0`, `openai>=1.0`, etc. peuvent installer des versions majeures incompatibles lors d'un futur déploiement.

Action recommandée : produire un lock contrôlé, activer une mise à jour automatisée, tester chaque mise à niveau et séparer les dépendances de production, développement et worker.

## Décision de conservation

| Élément | Décision |
|---|---|
| Flask + SQLAlchemy | Conserver pour les prochaines phases |
| Auth Flask-Login | Conserver et compléter |
| PostgreSQL Render | Conserver |
| Cloudinary | Conserver à court terme |
| OAuth Instagram officiel | Conserver et modulariser derrière un adaptateur |
| Publication Instagram actuelle | Conserver, sécuriser et rendre idempotente |
| Stripe | Conserver et fiabiliser |
| Templates Jinja | Conserver pour la Phase 0/1, puis évaluer un frontend composant |
| Prompt IA unique | Remplacer progressivement par des modules spécialisés |
| `db.create_all()` | Remplacer par des migrations |
| Serveur `python app.py` en production | Remplacer immédiatement |

## Niveau de maturité

| Domaine | Niveau / 5 |
|---|---:|
| Positionnement universel | 4 |
| Authentification | 2 |
| Brand Brain | 2 |
| Génération de contenu | 2 |
| Publication Instagram | 3 |
| Programmation autonome | 1 |
| Analytics | 0 |
| Optimisation IA | 0 |
| Multi-réseaux | 0 |
| Multi-marques / équipes | 0 |
| Facturation | 2 |
| Sécurité production | 2 |
| Observabilité | 1 |
| RGPD opérationnel | 0 |

## Conclusion

Le bon chemin est vertical : terminer complètement Instagram, le scheduler, les statuts, les analytics et la boucle d'apprentissage avant d'ouvrir Facebook, LinkedIn ou TikTok. La différenciation défendable de Commercia sera une intelligence de marque explicable qui décide, mesure et apprend, pas une simple multiplication de générateurs.
