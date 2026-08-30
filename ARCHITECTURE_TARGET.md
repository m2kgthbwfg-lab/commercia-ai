# Architecture cible progressive

L'objectif n'est pas de réécrire immédiatement le MVP. Les modules suivants seront extraits progressivement derrière des interfaces stables.

## Modules métier

- **Brand Intelligence** : collecte, validation et versionnement de la mémoire de marque.
- **Strategy Engine** : plateformes, piliers, formats, fréquence et objectifs.
- **Content Planner** : transforme une stratégie en idées et créneaux.
- **Copy Engine** : produit les textes et variantes adaptés au réseau.
- **Visual Engine** : prépare ou génère les médias lorsque le fournisseur est disponible.
- **Platform Adapter** : applique les contraintes de chaque réseau.
- **Publishing Engine** : planification, idempotence, retries et confirmation API.
- **Analytics Engine** : collecte et normalise les métriques.
- **Optimization Engine** : hypothèses, expériences et décisions explicables.
- **Safety & Quality Engine** : règles, sujets interdits, secteurs sensibles et contrôles qualité.

## Flux cible

1. Le Brand Brain fournit un contexte versionné.
2. Strategy Engine construit une stratégie approuvable.
3. Content Planner produit un plan éditorial.
4. Copy/Visual Engines créent des variantes.
5. Safety Engine valide ou demande une intervention.
6. Platform Adapter prépare le format final.
7. Publishing Engine programme et confirme la publication.
8. Analytics Engine collecte les résultats.
9. Optimization Engine propose une décision avec preuves et confiance.

## Infrastructure cible minimale

- web service Gunicorn ;
- PostgreSQL avec migrations ;
- file de tâches et worker ;
- scheduler ;
- stockage média ;
- cache/rate limiter partagé ;
- suivi d'erreurs et logs structurés ;
- secrets gérés par l'hébergeur ;
- sauvegardes et procédure de restauration.

## Règles d'architecture

- chaque job doit être idempotent ;
- chaque donnée appartient à un workspace ;
- chaque action automatisée possède un initiateur et une trace ;
- chaque métrique possède une source et une date ;
- chaque décision IA expose ses raisons ;
- aucune intégration sociale n'est marquée active avant une vérification réelle ;
- aucune publication n'est marquée publiée avant confirmation de l'API.
