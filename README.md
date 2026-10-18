# LucidNews

**Veille technologique fiable et newsletter IT.**

LucidNews surveille les sources importantes de l'écosystème IT, écarte le bruit, vérifie la fiabilité de chaque information, la classe, la résume en anglais et en français, puis la distribue (fichier Markdown, email, webhook).

```
Collecter → Filtrer → Vérifier → Classer → Résumer → Prioriser → Distribuer
```

> Statut : **Phase 1 — fondations techniques**. Pas encore d'interface : le produit tourne en ligne de commande et produit des digests Markdown et des emails.

---

## Sommaire

- [Fonctionnalités](#fonctionnalités)
- [Installation](#installation)
- [Configuration](#configuration)
- [Lancement](#lancement)
- [Démarrer l'application web](#démarrer-lapplication-web)
- [Tests](#tests)
- [Structure du dépôt](#structure-du-dépôt)
- [Documentation](#documentation)
- [Origine et licence](#origine-et-licence)

## Fonctionnalités

| Domaine | Ce que fait LucidNews |
|---|---|
| **Collecte** | 9 types de sources : RSS/Atom, Hacker News, GitHub (releases, activité), Reddit, Telegram, X/Twitter, OSS Insight, GDELT, Google News. Collecte en parallèle, rapport d'échec par source. |
| **Filtrage** | Fusion des doublons multi-sources (URL normalisée), score IA de 0 à 10 par profil, seuils par profil, dédoublonnage sémantique par sujet, quotas par catégorie. Une news que l'IA n'a pas pu noter n'est jamais publiée. |
| **Fiabilité** | Niveau de confiance de l'éditeur (officiel, reconnu, communautaire, inconnu) + vérification de l'affirmation par l'IA (confirmée, rapportée, non vérifiée, rumeur) → étiquette **Confirmé / Fiable / Non vérifié / Rumeur**. Une info non confirmée est toujours signalée comme telle. |
| **Classification** | Routage par profil éditorial (`tech-news`, `tech-blog`, `ai-creator`) et attribution de 1 à 3 catégories parmi 12 catégories IT. |
| **Résumé** | Enrichissement IA par blocs (résumé, contexte, impact, discussion), recherche web et recherche dans l'historique des digests, sources citées. |
| **Langues** | Anglais et français (le chinois reste disponible). Architecture extensible : une langue = une entrée dans `lucidnews/i18n.py`. |
| **Distribution** | Digest Markdown quotidien, email personnalisé par abonné (langue, catégories, sources, importance, fiabilité), webhooks (Slack, Discord, Feishu/Lark, DingTalk, générique), serveur MCP. |
| **Newsletter** | Abonnés, préférences, plans Free/Premium préparés (sans paiement), une version du digest par jeu de préférences. |

## Installation

Prérequis : Python ≥ 3.11 et [uv](https://github.com/astral-sh/uv).

```bash
git clone <url-du-depot> LucidNews
cd LucidNews
uv sync --extra dev
```

Extras optionnels :

```bash
uv sync --extra twitter   # X/Twitter en mode Playwright
```

Docker :

```bash
docker compose build
docker compose run --rm lucidnews --hours 24
```

## Configuration

Deux fichiers, tous deux **ignorés par git** :

| Fichier | Rôle |
|---|---|
| `.env` | Secrets (clés API, mots de passe). Modèle : [`.env.example`](.env.example). |
| `data/config.json` | Réglages : fournisseur IA, langues, sources, seuils, fiabilité, livraison. Modèle : [`data/config.example.json`](data/config.example.json). |

```bash
cp .env.example .env
cp data/config.example.json data/config.json
```

Règle importante : `ai.api_key_env` contient le **nom** d'une variable d'environnement, jamais la clé elle-même.

```json
"ai": { "enabled": false, "provider": "gemini", "model": "gemini-2.5-flash", "api_key_env": "GOOGLE_API_KEY", "languages": ["en", "fr"] }
```

Un assistant interactif peut aussi générer la configuration :

```bash
uv run lucidnews-wizard
```

Détails : [docs/configuration.md](docs/configuration.md) (référence complète) et [docs/architecture.md](docs/architecture.md#configuration).

### Activer l'analyse IA (facultatif)

LucidNews fonctionne **sans IA et sans aucune clé** : l'analyse est désactivée par défaut (`"ai": { "enabled": false }`). Le run collecte vos sources, fusionne les doublons, applique la fiabilité de l'éditeur, puis liste les news **sans analyse** (ni résumé, ni score, ni vérification de l'affirmation). Rien n'est envoyé à un fournisseur d'IA.

Pour activer l'analyse, deux étapes. Aucun fournisseur n'est imposé : prenez celui que vous voulez parmi `anthropic`, `openai`, `azure`, `gemini`, `deepseek`, `ali`, `doubao`, `minimax` ou `ollama` (local, sans clé).

1. **Activer.** Dans l'écran Réglages, cochez « Activer l'analyse par IA », ou mettez `"enabled": true` dans `data/config.json`. Choisissez le fournisseur et le modèle (`ai.provider`, `ai.model`) et le **nom** de la variable de la clé (`ai.api_key_env`).
2. **Fournir votre propre clé, hors de l'interface.** Elle ne se saisit jamais dans l'application web : celle-ci ne l'écrit pas, ne la lit pas et ne l'affiche pas. Elle indique seulement si la variable est détectée.

| Où lancez-vous LucidNews ? | Où mettre la clé |
|---|---|
| Sur votre machine | Dans le fichier `.env` (copié depuis `.env.example`, ignoré par git), par exemple `GOOGLE_API_KEY=...`, ou exportée dans le terminal. |
| GitHub Codespaces | Un secret Codespaces (GitHub › Settings › Codespaces › Secrets) : il devient une variable d'environnement du même nom. |
| GitHub Actions | Un secret du dépôt (Settings › Secrets and variables › Actions), transmis au pas qui lance LucidNews : `env: { GOOGLE_API_KEY: "${{ secrets.GOOGLE_API_KEY }}" }`. Le dépôt ne fournit pas de workflow : écrivez le vôtre. |
| Docker | `docker compose run -e GOOGLE_API_KEY …`, ou un fichier `.env` à côté de `docker-compose.yml`. |

Règles de sécurité :

- une clé ne va ni dans `data/config.json`, ni dans le code, ni dans un commit, ni dans le frontend ;
- une clé collée par erreur dans `ai.api_key_env` est refusée par l'écran Réglages ;
- une clé n'est jamais renvoyée par l'API, ni écrite dans les journaux ;
- sans clé détectée, l'analyse activée échoue proprement : les news restent listées sans analyse, le run ne plante pas.

Un quota épuisé ou un budget de tokens atteint produit le même résultat que « désactivée » pour la fin du run : les news restantes sont listées sans analyse.

### Comptes et connexion (facultatif)

Par défaut l'application web est ouverte, comme avant. Pour la protéger par des comptes (inscription et connexion par e-mail et mot de passe, ou avec Google), ajoutez dans `data/config.json` :

```json
"auth": { "enabled": true }
```

Pour **fermer les inscriptions** (recommandé dès que l'application est accessible à d'autres personnes), ajoutez `"allow_signup": false`. Les comptes se créent alors en terminal, par quelqu'un qui a accès au serveur :

```bash
uv run lucidnews-users add vous@example.com --name "Votre nom" --admin   # demande le mot de passe, sans l'afficher
uv run lucidnews-users add lecteur@example.com                         # un lecteur
uv run lucidnews-users list
uv run lucidnews-users role lecteur@example.com admin                  # ou reader
uv run lucidnews-users passwd vous@example.com                         # ferme aussi les sessions ouvertes
uv run lucidnews-users remove vous@example.com
```

**Créez votre compte administrateur avant d'activer `auth.enabled`** : sinon personne ne peut gérer la veille.

**Deux rôles.** Un **administrateur** a accès à tout : Sources, Préférences (abonnés), Qualité, Réglages et runs. Un **lecteur** ne voit que l'Édition et les Archives ; l'API lui refuse toute autre route (`403`), y compris une route ajoutée plus tard. Toute inscription par l'application ou par Google crée un lecteur ; un administrateur ne se crée qu'en terminal, et le dernier ne peut être ni rétrogradé ni supprimé. En passant à cette version, le compte le plus ancien d'une base existante devient administrateur.

**Mon compte** (menu du compte, en haut à droite) : chacun change son nom et son mot de passe, voit les appareils connectés et les déconnecte, télécharge ses données (JSON) et supprime son compte. Rien ne passe par e-mail : un mot de passe oublié est réinitialisé par un administrateur avec `lucidnews-users passwd`.

**Ma veille et Ma sélection** : dans Mon compte, chacun choisit ses domaines, une importance minimale, s'il veut voir les news non confirmées et des cartes complètes ou brèves. L'Édition affiche alors « Ma sélection », avec une bascule vers toute l'édition.

Avec les comptes, les écrans d'administration ne dépendent plus de l'adresse d'écoute : ils marchent derrière un reverse proxy (renseignez `public_url`), et c'est le rôle qui les protège. Sans comptes, ils restent réservés aux requêtes locales, comme avant.

Redémarrez `uv run lucidnews-api`. Toute l'API (sauf `/api/auth/*`) exige alors une session, et l'interface renvoie vers la page de connexion. **Aucune vérification d'e-mail** n'est demandée : le compte est utilisable tout de suite après l'inscription.

| Réglage (`auth.*`) | Défaut | Rôle |
|---|---|---|
| `enabled` | `false` | Active les comptes. |
| `allow_signup` | `true` | `false` ferme les inscriptions (e-mail et Google) : seuls les comptes existants se connectent. |
| `session_days` | `30` | Durée d'une session ; chaque utilisation la prolonge. |
| `public_url` | aucun | Adresse par laquelle le navigateur atteint l'application, par exemple `https://veille.example.com`. **Obligatoire derrière un reverse proxy et pour Google en dehors de localhost.** Avec `https`, le cookie de session devient `Secure`. |
| `google_client_id_env` | `GOOGLE_CLIENT_ID` | **Nom** de la variable qui contient l'identifiant client Google. |
| `google_client_secret_env` | `GOOGLE_CLIENT_SECRET` | **Nom** de la variable qui contient le secret client Google. |

Variables d'environnement (dans `.env`, jamais dans `config.json`) :

| Variable | Utilisation |
|---|---|
| `GOOGLE_CLIENT_ID` | Identifiant du client OAuth Google. Sans lui, le bouton « Continuer avec Google » n'apparaît pas : l'e-mail et le mot de passe fonctionnent seuls. |
| `GOOGLE_CLIENT_SECRET` | Secret du client OAuth Google (côté serveur uniquement : il n'est jamais envoyé au navigateur). |

Il n'y a pas d'autre secret à créer : les sessions sont gardées côté serveur (`data/auth.sqlite3`, droits 600), le navigateur ne reçoit qu'un identifiant aléatoire dans un cookie `HttpOnly`.

#### Configurer Google OAuth

1. Ouvrez la [console Google Cloud](https://console.cloud.google.com/), créez ou choisissez un projet.
2. **Google Auth Platform › Branding** (ou « Écran de consentement OAuth ») : renseignez le nom de l'application et une adresse d'assistance. **Audience** : « Externe ». Tant que l'application est en mode « Test », seuls les comptes ajoutés comme utilisateurs de test peuvent se connecter ; passez en production pour tout le monde. Les seules autorisations demandées sont `openid`, `email` et `profile` (non sensibles : aucune validation Google n'est requise).
3. **Clients › Créer un client** : type **Application Web**. Dans **URI de redirection autorisés**, ajoutez l'adresse **exacte** de retour :
   - développement avec Vite : `http://localhost:5173/api/auth/google/callback` ;
   - production : `https://VOTRE-DOMAINE/api/auth/google/callback` (la valeur de `public_url` + `/api/auth/google/callback`).
   Les « origines JavaScript autorisées » ne sont pas utilisées (le flux passe par le serveur).
4. Copiez l'identifiant et le secret dans `.env` :
   ```bash
   GOOGLE_CLIENT_ID=123456-abc.apps.googleusercontent.com
   GOOGLE_CLIENT_SECRET=GOCSPX-...
   ```
5. Redémarrez `uv run lucidnews-api`. Le bouton Google apparaît sur la page de connexion.

Pièges fréquents : `localhost` et `127.0.0.1` sont deux adresses différentes pour Google (utilisez celle de la barre d'adresse) ; le `http` n'est accepté que pour `localhost` ; l'erreur `redirect_uri_mismatch` signifie que l'adresse de l'étape 3 n'est pas identique à celle utilisée.

Sécurité, en bref : flux « code d'autorisation » avec PKCE, `state` à usage unique lié au navigateur, `nonce` vérifié dans le jeton, adresse e-mail Google obligatoirement vérifiée ; mots de passe hachés (scrypt, sel aléatoire) ; limitation des tentatives ; requêtes d'écriture refusées si leur origine n'est pas le site. Comme l'inscription par e-mail n'est pas vérifiée, un compte à mot de passe dont l'adresse se connecte ensuite avec Google **devient un compte Google** (son mot de passe est supprimé et ses autres sessions sont fermées) : sinon la personne qui s'est inscrite en premier avec l'adresse d'un autre garderait l'accès. Ne protège pas les routes de `lucidnews-public` (liens de confirmation et de désabonnement des newsletters), qui restent publiques par conception.

### Serveur et sécurité

Réglages du processus `lucidnews-api`, dans `data/config.json` (facultatifs) :

```json
"server": { "trusted_proxies": ["127.0.0.1", "::1"], "requests_per_minute": 240 }
```

| Réglage (`server.*`) | Défaut | Rôle |
|---|---|---|
| `trusted_proxies` | aucun | Adresses IP des reverse proxys autorisés à donner l'adresse du visiteur (`X-Forwarded-For`). **À renseigner derrière un proxy**, sinon tous les visiteurs partagent l'adresse du proxy et les limites de connexion les bloquent ensemble. |
| `requests_per_minute` | `240` | Requêtes par minute et par client sur l'API ; la recherche et la période ont droit au cinquième. Au-delà : `429` et `Retry-After: 60`. |

Chaque réponse de l'API porte des en-têtes de sécurité, et l'interface compilée une politique de sécurité du contenu (CSP). HTTPS, HSTS et `frame-ancestors` sont posés par le reverse proxy. Audit, modèle de menaces et liste ASVS : [docs/securite/](docs/securite/).

### Variables d'environnement

| Variable | Utilisation |
|---|---|
| `GOOGLE_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `AZURE_OPENAI_API_KEY` + `AZURE_OPENAI_ENDPOINT`, `DEEPSEEK_API_KEY`, `DASHSCOPE_API_KEY`, `DOUBAO_API_KEY`, `MINIMAX_API_KEY` | Clé du fournisseur IA choisi, **seulement si l'analyse IA est activée** (une seule suffit) |
| `LUCIDNEWS_OLLAMA_BASE_URL` | Adresse d'un serveur Ollama local (optionnel) |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | Connexion avec Google, seulement si `auth.enabled` (voir « Comptes et connexion ») |
| `GITHUB_TOKEN` | Relève la limite de l'API GitHub de 60 à 5000 requêtes/heure (recommandé) |
| `APIFY_TOKEN` | X/Twitter en mode Apify |
| `LWN_KEY` | Flux LWN en texte intégral (abonnés) |
| `EMAIL_PASSWORD` | Mot de passe SMTP/IMAP de la boîte newsletter |
| `LUCIDNEWS_WEBHOOK_URL` | URL du webhook |
| `LUCIDNEWS_PRESETS_URL` | Catalogue distant de sources pour l'assistant (sinon `data/presets.json`) |
| `LUCIDNEWS_PATH`, `LUCIDNEWS_MCP_SECRETS_PATH` | Serveur MCP |

Toute valeur de `config.json` peut référencer une variable avec `${NOM}`.

## Lancement

```bash
uv run lucidnews                # fenêtre définie par collection.time_window_hours (24 h par défaut)
uv run lucidnews --hours 8      # forcer une fenêtre
uv run lucidnews --log-level INFO
```

Résultats : `data/summaries/lucidnews-AAAA-MM-JJ-<langue>.md`, plus les emails et webhooks s'ils sont activés.

Autres commandes :

| Commande | Rôle |
|---|---|
| `uv run lucidnews-wizard` | Assistant de configuration |
| `uv run lucidnews-webhook` | Tester ou renvoyer un webhook |
| `uv run lucidnews-sources` | Santé des sources (mortes, en échec, silencieuses, bruyantes) |
| `uv run lucidnews-api` | API web du frontend (`frontend/`), sur localhost : archive en lecture, préférences des abonnés en local |
| `uv run lucidnews-public` | Service public séparé : liens de confirmation et de désinscription de la newsletter (voir `docs/newsletter.md`) |
| `uv run lucidnews-eval` | Mesure de la qualité de l'IA contre les news annotées à la main (voir `docs/evaluation.md`) |
| `uv run lucidnews-mcp` | Serveur MCP (pipeline par étapes pour agents IA) |
| `./scripts/daily-run.sh [heures]` | Exécution quotidienne (cron) |

## Démarrer l'application web

Deux processus, chacun dans son terminal, à lancer dans cet ordre.

**1. Backend (API Python)**, à la racine du dépôt :

```bash
uv run lucidnews-api
```

Écoute sur `http://127.0.0.1:8765`. Port ou dossier de données différents : `--port 8766`, `--data-dir chemin`.

**2. Frontend (React)** :

```bash
cd frontend
npm install        # première fois seulement
npm run dev
```

Ouvrir `http://localhost:5173`. Le frontend relaie `/api` vers `127.0.0.1:8765` ; pour une autre API : `LUCIDNEWS_API=http://127.0.0.1:8766 npm run dev`.

**Prérequis** : `uv sync` fait (voir Installation) et une archive existante (`uv run lucidnews` au moins une fois, ou le bouton « Lancer un run » dans Réglages une fois l'API démarrée). Sans archive, l'API refuse de démarrer.

### Redémarrer

- **Frontend** : `Ctrl+C` dans son terminal puis `npm run dev`. Rarement utile : Vite recharge seul à chaque modification.
- **Backend** : `Ctrl+C` puis `uv run lucidnews-api`. **À faire** après toute modification du code Python (nouvelles routes, rendu de l'e-mail…) ; un changement fait depuis la page Réglages est pris en compte sans redémarrer.
- **Port déjà occupé** : repérer le processus puis l'arrêter.

```bash
lsof -nP -iTCP:8765 -sTCP:LISTEN
```

```bash
kill <PID>
```

- **Version de production du frontend** : `npm run build` (dans `frontend/`) puis `npm run preview`.

## Tests

```bash
uv run pytest            # suite complète (aucun appel réseau ni IA réel)
uv run pytest -k reliability
```

La suite couvre la collecte (chaque scraper), la fusion des doublons, le filtrage, la classification, l'analyse, la fiabilité, la taxonomie, les langues, l'enrichissement, le rendu, la newsletter, le stockage, les webhooks, l'email, l'assistant et le serveur MCP.

Parcours de bout en bout (Playwright, sur l'interface compilée devant une API de test jetable, ports 8766 et 5174) :

```bash
cd frontend
npx playwright install chromium   # une seule fois
npm run e2e
```

La CI GitHub Actions lance tout à chaque push : pytest et pip-audit, oxlint, prettier, types, vitest, build et npm audit, puis les parcours Playwright.

Avant de livrer, faire aussi un vrai cycle : `uv run lucidnews --hours 6`, puis relire le digest produit.

## Structure du dépôt

```
lucidnews/
  main.py              point d'entrée CLI
  orchestrator.py      pipeline complet (collecte → distribution)
  models.py            modèles de données et schéma de configuration
  scrapers/            une classe par type de source
  extractors/          extraction du texte intégral des pages
  ai/                  clients IA, classification, analyse, enrichissement, rendu
  processing/          profils éditoriaux, outils (web, historique), sélection de contenu
  reliability/         confiance des sources et étiquettes de fiabilité
  taxonomy.py          12 catégories IT et niveaux d'importance
  i18n.py              langues et textes localisés
  newsletter/          abonnés, préférences, plans, sélection, plan d'envoi
  services/            email, webhook
  storage/             configuration, digests, abonnés (fichiers)
  mcp/                 serveur MCP
  setup/               assistant de configuration et catalogue de sources
profiles/              profils éditoriaux (prompts Markdown + JSON)
data/                  configuration d'exemple, catalogue de sources ; données locales ignorées par git
docs/                  documentation
tests/                 tests automatisés (pytest)
```

## Documentation

| Document | Contenu |
|---|---|
| [Architecture](docs/architecture.md) | Vue d'ensemble, flux de données, modules, configuration, points sensibles |
| [Collecte et sources](docs/collecte.md) | Fonctionnement de la collecte, catalogue de sources, ajout d'une source |
| [Fiabilité](docs/fiabilite.md) | Niveaux de confiance, vérification des affirmations, étiquettes, réglages |
| [Catégories et langues](docs/categories-et-langues.md) | Taxonomie IT, importance, langues, ajout d'une langue |
| [Newsletter](docs/newsletter.md) | Abonnés, préférences, plans, envoi |
| [Plan de lancement](Plan.md) | Lots restants jusqu'à la commercialisation, dépendances, critères mesurables |
| [Étude de marché](docs/etude-marche/rapport-lucidnews-2026-10.html) | Benchmark concurrentiel, besoins, audit, priorités, hébergement (octobre 2026) |
| [Roadmap technique](docs/roadmap.md) | Prochaines étapes |
| Références (en anglais) | [configuration](docs/configuration.md), [profils](docs/profiles.md), [score](docs/scoring.md), [scrapers](docs/scrapers.md), [extracteurs](docs/extractors.md), [cookies X](docs/twitter-cookies.md), [MCP](lucidnews/mcp/README.md) |

## Origine et licence

LucidNews est construit à partir du projet open source [Horizon](https://github.com/Thysrael/Horizon) (licence MIT, © 2026 Thysrael), dont il reprend le moteur de collecte et de traitement. Conformément à la licence MIT, la notice de copyright d'origine est conservée dans [LICENSE](LICENSE).
