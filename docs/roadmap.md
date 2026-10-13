# Roadmap technique

Le détail des lots clôturés et à venir est dans [lots.md](lots.md).

Priorités, dans cet ordre : **fiabilité → qualité des données → qualité des sources → stabilité → valeur réelle**. La monétisation et l'interface viennent ensuite.

## Phase 1 — Fondations (fait)

- Reprise du moteur Horizon, renommage en LucidNews, retrait de ce qui servait l'ancien produit (WeChat, finance/OpenBB, site Pages, références au serveur de l'auteur d'origine).
- Corrections de fiabilité : un item non noté n'est plus publié, apostrophes correctement rendues, profil `ai-creator` neutre en langue, sources GitHub normalisées, réessai des erreurs temporaires de classification, limiteur de débit IA.
- Fiabilité : registre de confiance des domaines, vérification des affirmations, étiquettes, consignes de rédaction prudente.
- Taxonomie des 12 catégories IT et niveaux d'importance.
- Langues : registre extensible, anglais et français complets.
- Newsletter : abonnés, préférences, plans Free/Premium (sans gating), envoi personnalisé par groupe de préférences.
- Catalogue de 31 flux IT vérifiés, documentation produit.

## Phase 2 — Qualité et stabilité des données

- **Corroboration** *(fait)* : les sites reconnus et indépendants qui rapportent le même événement sont comptés lors du dédoublonnage par sujet et font monter l'étiquette (règles dans `docs/fiabilite.md`). Étendue aux news sous le seuil et aux runs des 72 dernières heures via l'archive, et commande `lucidnews-reassess` pour recalculer les étiquettes archivées *(faits, lot 14 bis)*.
- **Santé des sources** *(fait)* : historique par source dans l'archive (statut, erreur, news collectées et retenues), classement `dead` / `failing` / `silent` / `noisy` / `healthy`, alerte en fin de run et commande `lucidnews-sources`. Score de qualité par source, utilisé pour départager les news de même score *(fait, lot 14 bis)*.
- **Archive d'items** *(fait)* : runs et news analysées stockés dans SQLite ; les analyses de news inchangées sont réutilisées. Ouvre la voie à l'envoi hebdomadaire, aux statistiques et à la reprise.
- **Robustesse IA** *(fait)* : nouvelle tentative en fin d'étape pour l'analyse et l'enrichissement, puis reprise des news non notées aux runs suivants depuis l'archive. Budget de tokens par run, quota épuisé géré sans bloquer le run (news publiées à part, sans analyse) et réutilisation de l'enrichissement *(faits, lot 14)*.
- **Évaluation** *(outil fait)* : annotation à l'aveugle dans l'écran Qualité, commande `lucidnews-eval` (sélection, importance, thèmes, affirmation, faux fiables), re-analyse avec `--rerun` pour tester un changement de consigne. Reste à faire : annoter au moins 30 news. Voir `docs/evaluation.md`.
- **Registre de confiance enrichi** *(fait)* : comptes de réseaux sociaux (X, Mastodon, Bluesky, Telegram) jugés sur leur compte et non sur la plateforme, éditeurs français et européens, autorités françaises et européennes, sites officiels de projets repérés dans l'archive. Reste à faire : poursuivre au fil des domaines inconnus.

## Phase 2 bis — Pilotage depuis l'interface

Objectif : utiliser LucidNews sans terminal pour les opérations courantes. Détail et ordre dans [lots.md](lots.md).

- Cartes d'actualité interactives (lot 15).
- Réglages : clés API (jamais réaffichées), IA, collecte et traitement (lot 16).
- Gestion des sources : ajout, modification, activation, suppression, test (lot 17).
- Domaines surveillés, couverture et sources recommandées (lot 18).
- Qualité de la veille : couverture, diversité, fraîcheur, doublons, fiabilité (lot 19).
- Lancement et planification des runs (lot 20).

## Phase 3 — Newsletter

- Contenu et préférences : envoi hebdomadaire, niveau de détail, aperçu, e-mail HTML refait (lot 21, fait).
- Envoi fiable : double opt-in, désinscription signée, fournisseur transactionnel, journal des envois, abonnés en base, fuseau horaire (lot 22).
- Recherche dans l'archive (lot 23), puis finitions de l'interface : mode sombre, contrastes, socle allégé (lot 24).

## Phase 4 — Comptes et SaaS (hors périmètre actuel)

- Comptes utilisateurs, authentification et rôles (lot 26).
- Activation des limites du plan Free et de l'offre Premium (`PLAN_LIMITS`), puis paiement.

## Dette technique identifiée (lot 25)

- Le paquet Python s'appelle `src` (héritage) ; le renommer en `lucidnews` demandera de mettre à jour tous les imports et les points d'entrée.
- `orchestrator.py` concentre beaucoup de responsabilités (≈ 1 100 lignes). À découper en étapes (`collect`, `select`, `deliver`) quand l'archive d'items arrivera.
- L'email HTML est un gabarit minimal ; il sera refait avec la phase UI.
- Les métadonnées fusionnées entre sources peuvent mélanger les auteurs (par exemple « Lobsters » affiché sur un item Hacker News).

## Phase 4 — Lancement commercial (plan du 13 octobre 2026)

Étude de marché, benchmark et audit : [rapport](etude-marche/rapport-lucidnews-2026-10.html).
Plan détaillé avec critères : [Plan.md](../Plan.md).

- **A. Finalisation fonctionnelle** : rôles et isolation (27), cycle de vie du compte avec
  vérification de l'e-mail (28), newsletter gérée par le lecteur (29).
- **B. Tests et sécurité** : ASVS niveau 1 (30), bout en bout et CI (31), preuve de qualité sur
  100 news annotées (12 bis).
- **C. Production** : exécution serveur hors macOS (32), e-mail authentifié et rebonds (33),
  sauvegardes (34), observabilité et coûts (35), conformité et CNDP (36).
- **D. Hébergement** : VPS + Docker Compose + Caddy (37), bêta privée de 20 à 50 lecteurs (38).
- **E. Après le lancement** : fil d'un événement, tendances, alertes, offres et paiement,
  équipes, sources personnelles, arabe, PostgreSQL (39 à 46).

