# Roadmap de transformation — Commercia AI

Cette roadmap privilégie un parcours complet et fiable plutôt qu'une accumulation de fonctions simulées.

## Phase 0 — Sécuriser la production

Objectif : pouvoir exploiter le MVP sans promesse trompeuse.

- exécuter le web service avec Gunicorn ;
- configurer `/health` ;
- introduire Flask-Migrate/Alembic ;
- verrouiller les dépendances ;
- centraliser les erreurs et logs structurés ;
- utiliser un stockage distribué pour le rate limiting ;
- ajouter les en-têtes de sécurité ;
- créer un cron ou worker réellement déployé ;
- rendre la publication idempotente et verrouillée ;
- afficher dans l'interface l'état réel du scheduler ;
- couvrir ce parcours avec des tests.

Critère de sortie : une publication programmée part réellement une seule fois, à l'heure prévue, et son échec est visible.

## Phase 1 — Fondations SaaS et Brand Brain

Objectif : créer une mémoire de marque structurée et modifiable.

- `Organization`, `Workspace`, `Membership`, `BrandMemory` ;
- migration du profil actuel sans perte ;
- onboarding progressif ;
- langue, fuseau, réseaux, logo, couleurs, règles, CTA et concurrents ;
- import et analyse contrôlée d'un site web ;
- écran de mémoire de marque ;
- vérification e-mail et récupération de compte ;
- suppression/export de compte ;
- audit logs fondamentaux.

Critère de sortie : chaque génération utilise une mémoire versionnée et l'utilisateur peut corriger les informations sources.

## Phase 2 — Content Engine et calendrier professionnel

Objectif : passer du JSON de campagne à des contenus éditables et planifiables.

- modules `Brand Intelligence`, `Strategy Engine`, `Content Planner`, `Copy Engine`, `Safety Engine` ;
- entités `ContentIdea`, `ContentPlan`, `Post`, `PostVariant`, `Approval` ;
- stratégie acceptée/modifiée par l'utilisateur ;
- calendrier jour/semaine/mois ;
- statuts Brouillon, À valider, Validé, Programmé, Publié, Échec, À corriger ;
- édition, déplacement, aperçu et versionnement ;
- génération asynchrone ;
- contrôle qualité et règles sectorielles sensibles.

Critère de sortie : une idée traverse tout le cycle jusqu'à un post validé sans données fictives.

## Phase 3 — Instagram vertical complet

Objectif : faire d'Instagram la première intégration totalement fiable.

- adaptateur réseau modulaire ;
- rafraîchissement et expiration des tokens ;
- reconnexion guidée ;
- images, carrousels, Reels et Stories seulement lorsque l'API les autorise ;
- webhooks et statuts confirmés ;
- annulation avant publication ;
- historique et erreurs actionnables ;
- file de tâches avec retries exponentiels et dead-letter queue ;
- niveaux Manuel, Assisté et Autopilot.

Critère de sortie : tous les statuts correspondent à une réalité confirmée par l'API.

## Phase 4 — Analytics Instagram réelles

Objectif : mesurer avant de recommander.

- snapshots compte et publications ;
- portée, impressions, vues, interactions et abonnés selon permissions ;
- normalisation des métriques ;
- dashboard sans données de démonstration ;
- indication claire des données indisponibles ;
- synchronisation périodique et reprise sur erreur.

Critère de sortie : chaque chiffre affiché possède une source, une date de collecte et un statut de fraîcheur.

## Phase 5 — Optimization Engine explicable

Objectif : apprendre par marque sans surinterpréter.

- `AIRecommendation`, `AIDecision`, `Experiment` ;
- seuil minimal de données ;
- hypothèses, confiance, raisons et métriques sources ;
- page « Décisions de Commercia » ;
- tests contrôlés sur hooks, CTA, sujets, formats et horaires ;
- possibilité d'annuler et de désactiver une famille de décisions.

Critère de sortie : une décision peut être retracée jusqu'aux données et annulée.

## Phase 6 — Autopilot avancé

Objectif : boucler Comprendre → Planifier → Créer → Publier → Mesurer → Optimiser.

- règles par catégorie ;
- limites de fréquence ;
- validations obligatoires ;
- arrêt d'urgence ;
- alertes ;
- veille légale et saisonnalité ;
- centre de contrôle quotidien ;
- recommandations et changements expliqués.

Critère de sortie : l'Autopilot peut fonctionner plusieurs semaines sans publication hors règle ni perte de contrôle.

## Phase 7 — Deuxième réseau

Objectif : valider l'architecture multi-réseaux avec une intégration officielle priorisée par la demande client et l'accès API.

- adapter la stratégie au réseau ;
- ne pas republier le même texte partout ;
- réutiliser le cœur de planification, sécurité, statuts et analytics ;
- afficher les limites exactes de l'API.

Critère de sortie : le deuxième réseau atteint le même niveau de fiabilité qu'Instagram.

## Phase 8 — Agences, multi-marques et scale

- plusieurs marques par workspace ;
- rôles et permissions ;
- validation client ;
- commentaires internes ;
- facturation par capacité ;
- rapports ;
- workers horizontaux ;
- isolation renforcée ;
- SLO, alertes et reprise après incident.

## Priorités immédiates

| Priorité | Travail | Pourquoi |
|---|---|---|
| P0 | Gunicorn + health check réel | Le serveur actuel n'est pas adapté à la production |
| P0 | Déployer le scheduler | L'Autopilot n'exécute rien actuellement en production |
| P0 | Verrouillage et idempotence | Éviter toute double publication |
| P0 | Migrations | Faire évoluer la base sans risque |
| P1 | Statuts et logs visibles | Permettre au client de comprendre un échec |
| P1 | Token lifecycle Instagram | Éviter les interruptions silencieuses |
| P1 | Brand Brain structuré | Base de la personnalisation différenciante |
| P1 | Calendrier éditable | Cœur du travail quotidien |
| P2 | Analytics Instagram | Prérequis à toute optimisation réelle |
| P2 | Optimization Engine | Différenciation majeure de Commercia |

## Ce qui ne doit pas être construit maintenant

- faux dashboard analytics ;
- logos de réseaux non connectés laissant penser qu'ils fonctionnent ;
- inbox simulée ;
- recommandations sans données ;
- génération vidéo sans fournisseur et budget définis ;
- expansion multi-réseaux avant la fiabilité Instagram.
