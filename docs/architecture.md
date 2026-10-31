# Architecture

LucidNews est une application Python asynchrone en ligne de commande. Elle n'a ni base de données ni interface pour l'instant : tout l'état vit dans des fichiers sous `data/`.

## Vue d'ensemble

```
             ┌────────────────────── lucidnews/orchestrator.py (PipelineOrchestrator.run) ──────────────────────┐
 sources ──▶ │ 1 Collecte ─▶ 2 Fusion ─▶ 3 Classification ─▶ 4 Analyse ─▶ 5 Fiabilité ─▶ 6 Filtrage      │
 (scrapers)  │   parallèle    doublons     (profil)          score, catégories, claim    seuils, dédup     │
             │                                                                            sujet, quotas    │
             │ ─▶ 7 Enrichissement (par langue) ─▶ 8 Rendu Markdown ─▶ 9 Distribution                     │
             │      résumé, contexte, impact         par langue          fichier, email (par abonné),     │
             │      + recherche web / historique                         webhook                          │
             └─────────────────────────────────────────────────────────────────────────────────────────────┘
```

| Étape | Module | Rôle | IA ? |
|---|---|---|---|
| 1 Collecte | `scrapers/*`, `extractors/*` | Une classe par type de source, toutes lancées en parallèle. Une source en échec n'arrête pas les autres ; si **toutes** échouent, le run s'arrête en erreur. | Non |
| 2 Fusion | `orchestrator.merge_cross_source_duplicates` | Regroupe les items qui pointent vers la même URL normalisée (sans `utm_*`, `fbclid`…), garde le contenu le plus riche et fusionne les métadonnées. | Non |
| 3 Classification | `ai/classifier.py` | Choisit le profil éditorial : forcé par la source (`profile`), ou choisi par l'IA (`"auto"` ou liste de candidats). Les erreurs temporaires du fournisseur sont réessayées. | Oui |
| 4 Analyse | `ai/analyzer.py`, `ai/prompting/analysis.py` | Note de 0 à 10 selon la grille du profil, résumé d'une phrase, tags, 1 à 3 catégories IT, statut de l'affirmation. | Oui |
| 5 Fiabilité | `reliability/assess.py` | Combine la confiance de l'éditeur et le statut de l'affirmation → étiquette. Déterministe. | Non |
| 6 Filtrage | `orchestrator.select_digest_items` | Seuil par profil, exclusion des items non notés et des étiquettes exclues, dédoublonnage sémantique par sujet (IA), quotas par catégorie, plafond global. | Partiel |
| 7 Enrichissement | `ai/enricher.py`, `processing/tools.py` | Pour chaque langue, génère les blocs du profil (résumé, contexte…), avec recherche web (DuckDuckGo) et recherche BM25 dans les digests précédents. | Oui |
| 8 Rendu | `ai/summarizer.py`, `i18n.py` | Markdown produit par du code (pas d'IA), avec échappement strict des contenus non fiables. | Non |
| 9 Distribution | `storage/`, `newsletter/`, `services/` | Digest dans `data/summaries/`, email par jeu de préférences, webhooks. | Non |

## Modules

| Chemin | Responsabilité |
|---|---|
| `lucidnews/main.py` | CLI `lucidnews` : charge `.env` et la config, lance l'orchestrateur |
| `lucidnews/orchestrator.py` | Enchaîne les étapes ; seul endroit qui connaît tout le pipeline (`run`, enrichissement, analyse, archive) |
| `lucidnews/pipeline/` | Étapes assemblées par l'orchestrateur : `collect.py` (collecte, doublons entre sources), `select.py` (filtres, digest équilibré), `deliver.py` (newsletters) |
| `lucidnews/models.py` | Modèles Pydantic des items (`ContentItem`, `ProcessingResult`…) et **schéma complet de la configuration** (`Config`) |
| `lucidnews/scrapers/` | `BaseScraper.fetch(since) → list[ContentItem]` pour chaque source |
| `lucidnews/extractors/` | Extraction du texte intégral d'une page (trafilatura) pour les flux RSS tronqués |
| `lucidnews/ai/client.py` | Clients IA (OpenAI, Anthropic, Gemini, Azure, DeepSeek, Ollama…), chaîne de repli entre fournisseurs, limiteur de débit |
| `lucidnews/ai/classifier.py`, `analyzer.py`, `enricher.py` | Étapes IA |
| `lucidnews/ai/prompting/` | Construction des prompts (règles de preuve communes, catégories, vérification) |
| `lucidnews/ai/summarizer.py` | Rendu Markdown du digest et des messages webhook |
| `lucidnews/processing/profiles.py` | Chargement et validation des profils éditoriaux (`profiles/*/profile.json`) |
| `lucidnews/processing/tools.py`, `history.py` | Outils d'enrichissement : recherche web, recherche dans l'historique |
| `lucidnews/reliability/` | Registre de confiance des domaines, règles de combinaison, types |
| `lucidnews/taxonomy.py` | 12 catégories IT, alias, libellés, niveaux d'importance ; lecture des catégories de tous les secteurs |
| `lucidnews/sectors.py` | Secteurs (lot 47) : un secteur par installation (`Config.sector`, défaut `tech`), ses catégories et leur portée pour l'IA ; identifiants uniques entre secteurs |
| `lucidnews/i18n.py` | Registre des langues, textes fixes du digest, format des dates |
| `lucidnews/archive/` | Archive SQLite des runs et des news ; réutilisation des analyses ; compteurs de sélection par run (schéma 5) |
| `lucidnews/quality_overview.py` | Indicateurs de la page Qualité : couverture, diversité, santé, fraîcheur, doublons, filtrage, fiabilité publiée |
| `lucidnews/source_health.py`, `lucidnews/sources_cli.py` | Identifiants de source, résultat par run, classement de santé, commande `lucidnews-sources` |
| `lucidnews/source_quality.py` | Score de qualité par source (départage des news de même score) |
| `lucidnews/auth/` | Comptes facultatifs : `service.py` (routes `/api/auth/*`, sessions, limitation), `store.py` (SQLite `data/auth.sqlite3`), `passwords.py` (scrypt), `google.py` (OAuth 2.0 + PKCE) |
| `lucidnews/settings_api.py` | Réglages depuis l'interface : édition brute de `config.json`, copies de sauvegarde ; état (présente ou non, jamais la valeur) des variables de clés. Aucune clé n'est écrite |
| `lucidnews/coverage.py` | Couverture des 12 catégories par les sources, calculée sur l'archive ; lacunes des domaines suivis |
| `lucidnews/source_catalog.py` | Catalogue des sources recommandées (config d'exemple et catalogue de l'assistant), sans les sources déjà configurées |
| `lucidnews/run_lock.py` | Verrou d'un run à la fois (terminal, interface, planification) |
| `lucidnews/runs_api.py` | Lancer le pipeline depuis l'interface, suivre son journal, planification launchd |
| `lucidnews/sources_api.py` | Sources depuis l'interface : liste avec la clé de santé, ajout, modification, suppression, test d'une source sans IA |
| `lucidnews/reassess_cli.py` | Commande `lucidnews-reassess` : recalcul des étiquettes de l'archive avec le registre actuel |
| `lucidnews/evaluation/` | Annotations humaines, calcul des scores (sélection, importance, thèmes, affirmation, faux fiables), commande `lucidnews-eval` |
| `lucidnews/web_api.py`, `lucidnews/subscribers_api.py` | API HTTP du frontend : archive en lecture (éditions, news, sources), préférences des abonnés en écriture locale, commande `lucidnews-api` |
| `lucidnews/newsletter/` | Abonnés, préférences, plans, sélection, plan d'envoi, stockage |
| `lucidnews/services/email.py` | SMTP (envoi) et IMAP (inscription / désinscription par email) |
| `lucidnews/services/webhook.py` | Webhooks génériques et plateformes (Slack, Discord, Feishu/Lark, DingTalk) |
| `lucidnews/storage/manager.py` | Lecture de la config (avec `${VAR}`), écriture atomique des digests, accès abonnés |
| `lucidnews/mcp/` | Serveur MCP : le même pipeline exposé par étapes (`ln_fetch_items`, `ln_score_items`…) |
| `lucidnews/setup/` | Assistant `lucidnews-wizard` et catalogue `data/presets.json` |
| `profiles/` | Profils éditoriaux : `match.md` (routage), `analysis.md` (grille de score), `enrichment.md` (rédaction) |

## Données

Un item traverse le pipeline sous la forme d'un `ContentItem` :

```
ContentItem
├── id, source_type, title, url, content, author, published_at
├── metadata            (feed_name, category, discussion_url, score HN, source_trust, merged_sources…)
├── profile             (routage demandé par la source)
└── processing: ProcessingResult
    ├── classification  (profil retenu, méthode, confiance)
    ├── analysis        (score, reason, summary, tags, categories, claim{status, evidence})
    ├── reliability     (label, source_tier, source_domain, claim_status, reasons)
    └── artifacts[lang] (titre localisé, blocs, sources citées)
```

Fichiers sous `data/` :

| Fichier | Contenu | Git |
|---|---|---|
| `config.json` | Configuration locale | ignoré |
| `config.example.json` | Modèle de configuration et catalogue de sources de référence | suivi |
| `presets.json` | Catalogue de sources pour l'assistant | suivi |
| `summaries/lucidnews-AAAA-MM-JJ-<lang>.md` | Digests produits ; servent aussi d'historique pour l'enrichissement | ignoré |
| `subscribers.json` | Abonnés newsletter (format versionné) | ignoré |
| `archive.sqlite3` | Archive des runs et des news traitées (voir plus bas) | ignoré |
| `mcp-runs/` | Étapes intermédiaires du serveur MCP | ignoré |

## Configuration

Toute la configuration est centralisée dans un seul schéma, `Config` (`lucidnews/models.py`), chargé depuis `data/config.json` :

| Section | Rôle |
|---|---|
| `ai` | Fournisseur, modèle, `api_key_env` (nom de variable), langues de sortie, concurrence, `max_requests_per_minute`, chaîne de repli |
| `sources` | Sources à surveiller, avec pour chacune `category`, `profile` et, pour RSS, `trust` |
| `collection` | Fenêtre de temps (`time_window_hours`) |
| `processing` | Dossier des profils, profil par défaut, seuil et dédoublonnage par profil |
| `reliability` | Surcharges du registre de domaines, étiquettes à exclure du digest |
| `archive` | Archive SQLite : activation, chemin, réutilisation des analyses |
| `digest` | Ordre des sections, quotas par catégorie, plafond d'items |
| `email`, `webhook` | Distribution |
| `extractors`, `display` | Extraction de texte intégral, icônes du terminal |

Les secrets ne vont jamais dans ce fichier : il contient des **noms** de variables (`api_key_env`, `password_env`, `url_env`) ou des références `${VAR}`.

## Archive

Chaque run est enregistré dans `data/archive.sqlite3`, une base SQLite (une base de données contenue dans un seul fichier, sans serveur).

| Table | Contenu |
|---|---|
| `runs` | Un run : début, fin, statut (`running`, `success`, `empty`, `failed`), fenêtre, nombre de news collectées et retenues, rapport de collecte, erreur |
| `items` | Une ligne par news (identifiant stable de la source), avec son état le plus récent : JSON complet, score, fiabilité, catégories |
| `run_items` | Quelles news chaque run a vues et retenues |
| `source_runs` | Résultat de chaque source à chaque run : statut, erreur, news collectées et retenues |

Usages :

- **Réutilisation des analyses** : si une news revient inchangée (même titre, URL, contenu et routage), son analyse est reprise au lieu de rappeler l'IA. On peut le désactiver avec `archive.reuse_analysis: false`, par exemple après un changement de consigne.
- **Réutilisation de l'enrichissement** : avec une analyse reprise, l'enrichissement (titre traduit, résumé, contexte) est repris aussi s'il existe dans toutes les langues configurées. Désactivable avec `archive.reuse_enrichment: false`.
- **Quota IA épuisé** : quand le budget de tokens du run (`ai.max_tokens_per_run`) est atteint, ou que le fournisseur annonce son quota épuisé, l'IA n'est plus appelée du tout jusqu'à la fin du run. Les news pas encore analysées sont marquées `ai_skipped`, reprises au run suivant sans consommer de tentative, et une partie est publiée à part, sans analyse (voir [fiabilite.md](fiabilite.md)). Chaque run garde la raison (`ai_limit`), les tokens utilisés (`tokens_used`) et le nombre de news non analysées (`ai_skipped_count`).
- **Recherche plein texte** : table FTS5 `items_fts` (titres, résumés, tags, enrichissement, accents ignorés), mise à jour à chaque `record_items`, reconstruite à l'ouverture d'une archive qui n'en a pas ; voir `lucidnews/archive/search.py` et `GET /api/search`.
- **Historique** : `ItemArchive.items_between(depuis, jusqu_a, selected_only=...)` sert de base à l'envoi hebdomadaire (7 derniers jours) et aux statistiques de sources.
- **Reprise des échecs** : une news que l'IA n'a pas pu noter est d'abord retentée une fois en fin d'analyse, après une pause (`ai.failed_retry_delay_sec`). Si elle échoue encore, elle reste « en attente » dans l'archive et est reprise aux runs suivants, dans la limite de `archive.max_analysis_attempts` runs et de `archive.retry_window_hours` heures. L'enrichissement raté est aussi retenté une fois. Chaque run garde le nombre de news restées non notées (`unscored_count`).
- L'archive est « au mieux » : si elle est inaccessible, le run continue et produit le digest, avec un avertissement.

## Points sensibles

Ces parties portent la qualité et la fiabilité du produit. Toute modification doit être accompagnée de tests.

- **Scrapers** : chaque source a ses particularités (dates, pagination, limites d'API). Un scraper doit renvoyer `[]` plutôt que lever une exception pour une erreur réseau ponctuelle ; le rapport de collecte (`FetchReport`) distingue succès, vide et échec.
- **Fusion des doublons** : la clé d'URL est volontairement prudente (pas de suppression de paramètres autres que le tracking).
- **Filtrage** : un item non noté ne passe jamais ; les items sont toujours triés par score décroissant.
- **Prompts** (`ai/prompting/`, `profiles/`) : ils imposent de ne rien inventer et de traiter tout contenu collecté comme des données, pas des instructions (protection contre l'injection de prompt).
- **Rendu** : tout texte venant d'une source ou de l'IA est échappé (HTML et Markdown) ; seules les URL `http(s)` sont rendues en lien.
- **Fiabilité** : les règles de `reliability/assess.py` sont conservatrices par conception ; ne pas les assouplir sans décision produit.
- **Quotas IA** : régler `ai.max_requests_per_minute` selon l'offre du fournisseur, sinon les erreurs 429 font perdre des items (non notés, donc exclus). Le quota épuisé (journalier ou budget du run) est géré à part par `ai/budget.py` : un appel refusé échoue tout de suite, sans attente ni nouvelle tentative.
- **News sans analyse** : elles ne sont publiées que si le quota est épuisé, jamais pour une autre erreur. Elles portent toujours l'étiquette « Non vérifié » et n'affichent que des données de la source.
