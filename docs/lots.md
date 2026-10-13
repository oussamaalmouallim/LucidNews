# Lots de travail — LucidNews

Ce document regroupe tous les lots : ceux qui sont **clôturés** et ceux qui
**restent à faire**. Il complète la [roadmap](roadmap.md), qui donne les priorités.

État au 13 octobre 2026. Dernier lot clôturé : lot 25 bis ; lot 26 commencé (authentification).

**Suite du plan** : depuis l'étude de marché du 13 octobre 2026, les lots 27 à 46 sont décrits dans [Plan.md](../Plan.md), avec leurs critères mesurables. Ce fichier garde l'historique et les lots en cours.

Légende : ✅ clôturé · 🟡 outil livré, action humaine attendue · ⏳ proposé, en attente de décision · 📋 planifié.

---

## Sommaire

**Lots clôturés**

- [Lot 0 — Analyse d'Horizon et clé API](#lot-0--analyse-dhorizon-et-clé-api) ✅
- [Lot 1 — Refonte en LucidNews (phase 1)](#lot-1--refonte-en-lucidnews-phase-1) ✅
- [Lot 2 — Archive SQLite des runs et des news](#lot-2--archive-sqlite-des-runs-et-des-news) ✅
- [Lot 3 — Robustesse face aux échecs de l'IA](#lot-3--robustesse-face-aux-échecs-de-lia) ✅
- [Lot 4 — Santé des sources](#lot-4--santé-des-sources) ✅
- [Lot 5 — Corroboration par des sources indépendantes](#lot-5--corroboration-par-des-sources-indépendantes) ✅
- [Lot 6 — Direction UI et dépendances](#lot-6--direction-ui-et-dépendances) ✅
- [Lot 7 — API web et écran Édition du jour](#lot-7--api-web-et-écran-édition-du-jour) ✅
- [Lot 8 — Écrans Archives et Santé des sources](#lot-8--écrans-archives-et-santé-des-sources) ✅
- [Lot 9 — Fiche d'une news](#lot-9--fiche-dune-news) ✅
- [Lot 10 — Écran Préférences (version locale)](#lot-10--écran-préférences-version-locale) ✅
- [Lot 11 — Mesure de la qualité](#lot-11--mesure-de-la-qualité) 🟡
- [Lot 13 — Registre de confiance enrichi](#lot-13--registre-de-confiance-enrichi) ✅
- [Lot 14 — Budget IA et quota épuisé](#lot-14--budget-ia-et-quota-épuisé) ✅
- [Lot 14 bis — Corroboration élargie et qualité des sources](#lot-14-bis--corroboration-élargie-et-qualité-des-sources) ✅
- [Lot 15 — Cartes d'actualité interactives](#lot-15--cartes-dactualité-interactives) ✅
- [Lot 16 — Socle de pilotage et page Réglages](#lot-16--socle-de-pilotage-et-page-réglages) ✅

**Lots suivants** (dans l'ordre d'exécution)

- [Ordre d'exécution et dépendances](#ordre-dexécution-et-dépendances)
- [Navigation visée](#navigation-visée)
- [Lot 12 — Annoter au moins 30 news](#lot-12--annoter-au-moins-30-news) 🟡
- [Lot 17 — Gestion des sources](#lot-17--gestion-des-sources) ✅
- [Lot 18 — Domaines surveillés et couverture](#lot-18--domaines-surveillés-et-couverture) ✅
- [Lot 19 — Qualité de la veille](#lot-19--qualité-de-la-veille) ✅
- [Lot 20 — Lancer et planifier les runs](#lot-20--lancer-et-planifier-les-runs) ✅
- [Lot 21 — Newsletter : contenu et préférences](#lot-21--newsletter--contenu-et-préférences) ✅
- [Lot 22 — Newsletter : envoi fiable](#lot-22--newsletter--envoi-fiable) ✅
- [Lot 23 — Recherche dans l'archive](#lot-23--recherche-dans-larchive) ✅
- [Lot 24 — Finitions de l'interface](#lot-24--finitions-de-linterface) ✅
- [Lot 25 — Dette technique](#lot-25--dette-technique) ✅
- [Lot 25 bis — IA facultative et clés hors de l'interface](#lot-25-bis--ia-facultative-et-clés-hors-de-linterface) ✅
- [Lot 26 — Comptes et SaaS (phase 4)](#lot-26--comptes-et-saas-phase-4) 🟡
- [Lots 27 à 46 — Plan de lancement](#lots-27-à-46--plan-de-lancement) 📋
- [Paramètres : où ils vivent](#paramètres--où-ils-vivent-et-comment-ils-sappliquent)
- [Blocages et décisions en attente](#blocages-et-décisions-en-attente)
- [Analyse : besoins d'une newsletter moderne](#analyse--besoins-dune-newsletter-moderne)

**Annexes**

- [Points observés à confirmer](#points-observés-à-confirmer)
- [Décisions prises](#décisions-prises)
- [Historique des commits](#historique-des-commits)

---

# Lots clôturés

## Lot 0 — Analyse d'Horizon et clé API

✅ Clôturé · Travail fait dans le clone Horizon, avant la refonte (aucun commit LucidNews).

**Objectif** : comprendre le projet d'origine sans rien modifier, puis corriger l'erreur « Missing API key ».

**Fait**

- Analyse complète du moteur Horizon (collecte, analyse IA, enrichissement, rendu, envoi).
- Cause de l'erreur : le champ `api_key_env` contenait la **valeur** de la clé au lieu du **nom** de la variable. Corrigé en `GEMINI_API_KEY`.
- Vérification des news du digest du 5 octobre 2026 : les faits étaient exacts. Les défauts relevés (news non notées publiées, apostrophes mal affichées, etc.) ont été traités au lot 1.

---

## Lot 1 — Refonte en LucidNews (phase 1)

✅ Clôturé · Commits `57432f9` → `c01db56` · Dépôt privé `oussamaalmouallim/LucidNews`.

**Objectif** : transformer Horizon en produit propre, sans casser la collecte ni la fiabilité, avec un historique Git neuf et sans secret.

**Choix validés**

- Nom : **LucidNews**.
- Retirés : WeChat, README chinois et japonais, site GitHub Pages, Finance et OpenBB.
- Gardé : le profil `ai-creator`, traduit en anglais.
- Langues : anglais et français, extensibles.
- Aucune interface, aucun paiement, aucun paywall dans cette phase.

**Fait**

| Sujet | Contenu |
|---|---|
| Socle | Import d'Horizon (licence MIT, mention © 2026 Thysrael conservée), renommage complet, retrait des fonctions de l'ancien produit. |
| Corrections | Une news non notée n'est plus jamais publiée. Apostrophes lisibles dans le digest et l'e-mail. Préfixe d'angle traduit. Sources GitHub normalisées. Sélection et rendu durcis. |
| Fiabilité | Registre de confiance des domaines (officiel, reconnu, communautaire, inconnu). Statut de l'affirmation donné par l'IA. Étiquettes Confirmé / Fiable / Non vérifié / Rumeur. Consigne de rédaction prudente : une info non confirmée n'est jamais présentée comme un fait. |
| Taxonomie | 12 catégories IT et 4 niveaux d'importance. |
| Langues | Registre extensible, textes EN et FR complets, repli sur l'anglais. |
| Newsletter | Abonnés, préférences, offres Free et Premium (sans limite), envoi par groupe de préférences. |
| Sources | Catalogue de 31 flux IT vérifiés, environnement documenté. |
| IA | Limiteur de requêtes par minute (quota Gemini gratuit), nouvelles tentatives du classifieur. |
| Sécurité | Fichiers de config locaux, variantes `.env` et fichiers de clés ignorés. Historique Git vérifié sans secret. Image Docker vérifiée sans secret. |
| Docs | README et docs produit en français (architecture, collecte, fiabilité, catégories et langues, newsletter, roadmap). Docs techniques en anglais (configuration, profils, scrapers). SECURITY.md. |

**Incidents traités**

- Erreurs 429 et 503 de Gemini (offre gratuite) : limiteur, nouvelles tentatives, changement de modèle.
- Flux CISA bloqué (403) quel que soit l'agent : flux retiré plutôt que de contourner la protection anti-robot.
- Flux Mozilla (403) : corrigé avec un agent HTTP honnête qui se présente comme LucidNews.

---

## Lot 2 — Archive SQLite des runs et des news

✅ Clôturé · Commit `933b55a` · Étape 1 de la phase 2.

**Objectif** : garder l'historique de chaque run et ne pas repayer l'analyse d'une news déjà vue.

**Fait**

- Base SQLite locale : runs, news, liens run ↔ news (retenue ou non).
- Réutilisation de l'analyse quand le contenu d'une news n'a pas changé.
- Bug corrigé pendant le test : l'enregistrement avant analyse écrasait l'analyse stockée, donc rien n'était réutilisé. Désormais l'écriture se fait après l'analyse, et la base refuse de remplacer une analyse par une copie non analysée.
- Vérifié sur un vrai run : 12 analyses sur 12 réutilisées, environ 70 % de tokens en moins.

---

## Lot 3 — Robustesse face aux échecs de l'IA

✅ Clôturé · Commit `47b4110` · Étape 2 de la phase 2.

**Objectif** : ne plus perdre une news parce que l'IA a échoué une fois.

**Fait**

- Nouvelle tentative en fin d'étape, après une pause, pour l'analyse et l'enrichissement.
- Les news restées non notées sont reprises aux runs suivants depuis l'archive, dans une fenêtre de temps et un nombre d'essais limités.
- Le nombre de news non notées est enregistré pour chaque run.

---

## Lot 4 — Santé des sources

✅ Clôturé · Commit `f2269ab` · Étape 3 de la phase 2.

**Objectif** : savoir quelles sources marchent, échouent ou n'apportent rien.

**Fait**

- Résultat de chaque source à chaque run, stocké dans l'archive.
- Classement : morte, en échec, silencieuse, bruyante, saine.
- Alerte en fin de run, limitée aux sources encore configurées.
- Commande `lucidnews-sources` (tableau ou JSON, filtres par statut et par période, option pour inclure les sources retirées).
- Erreurs suivies source par source pour les flux RSS et les dépôts GitHub.
- Config locale nettoyée : 5 flux hors sujet et 6 sources mortes retirés. Il reste 23 flux RSS et 5 sources GitHub.

---

## Lot 5 — Corroboration par des sources indépendantes

✅ Clôturé · Commit `54f0e88` · Étape 4 de la phase 2.

**Objectif** : quand plusieurs sites sérieux rapportent le même événement, en tenir compte dans la fiabilité.

**Règles**

| Situation | Étiquette |
|---|---|
| L'acteur concerné publie aussi l'info | Confirmé |
| Source faible + 1 site reconnu indépendant | Fiable |
| Affirmation non vérifiée + 2 sites reconnus | Fiable |
| Rumeur, même répétée | Reste Rumeur |

- Les sous-domaines d'un même site comptent pour un seul site.
- Les forums et sites inconnus ne comptent pas.
- Affichage dans le digest : « corroboré par N source(s) indépendante(s) ».

**Limite** : pas encore observée sur un vrai run, aucun sujet n'a été fusionné. Le comportement est couvert par les tests.

---

## Lot 6 — Direction UI et dépendances

✅ Clôturé · Inclus dans le commit `9e0496c`.

**Objectif** : fixer la direction visuelle à partir des modèles, sans copier ce qui ne sert pas une newsletter.

**Fait**

- Deux modèles analysés avec la méthode de la skill UI-Stealer : « Agenta » pour l'ambiance, « Paypay » pour la structure des écrans.
- Analyse détaillée : structure, composants, espacements, typographie, cartes, boutons, champs, tableaux, graphiques, effets, animations, responsive, détails visuels.
- Éléments écartés : violets criards, bloc noir, chiffres marketing, icônes 3D, flux de paiement.
- Couleurs propres à LucidNews. La fiabilité a sa propre gamme, distincte de la couleur d'accent.
- Deux polices : Plus Jakarta Sans pour l'interface, Newsreader pour la lecture.
- Liste des dépendances : chaque paquet est justifié, avec l'option écartée.

**Documents** : [frontend/docs/direction-ui.md](../frontend/docs/direction-ui.md), [frontend/docs/dependances.md](../frontend/docs/dependances.md).

---

## Lot 7 — API web et écran Édition du jour

✅ Clôturé · Commit `9e0496c`.

**Fait**

- Commande `lucidnews-api` : lit l'archive sans jamais l'écrire, écoute en local, aucune dépendance Python ajoutée.
- Application React : React 19, Vite, Tailwind 4, motion, TanStack Query, zod.
- Écran Édition du jour :
  - bandeau avec date et compteurs ;
  - une carte par news : importance, score, étiquette de fiabilité, avertissement si l'info n'est pas confirmée, catégories, bouton « Lire la suite » ;
  - colonne de droite qui reste visible : sommaire des rubriques, répartition de la fiabilité.
- Passage EN/FR (la langue est dans l'URL), bouton « animations off », respect du réglage « réduire les animations ».

**Bugs corrigés pendant les tests** : compteurs à valeur négative, cartes invisibles quand les animations sont coupées, colonne de droite non fixe.

---

## Lot 8 — Écrans Archives et Santé des sources

✅ Clôturé · Commit `9e0496c`.

**Fait**

- Archives : calendrier (seuls les jours avec une édition sont cliquables) et liste des éditions par jour.
- Santé des sources : chiffres clés, graphique « Volume par run » avec une vue Tableau, tableau filtrable par statut, période de 7, 14 ou 30 jours.
- Couleurs du graphique validées pour le daltonisme et le contraste.
- Navigation en barre flottante en bas sur téléphone.
- Un fichier JS par écran.
- Port de l'API configurable (variable `LUCIDNEWS_API`).

**Bugs corrigés** : « 1 retenus », chiffres à zéro colorés en alerte.

---

## Lot 9 — Fiche d'une news

✅ Clôturé · Commit `2e77a82`.

**Fait**

- Route `/api/items/<id>` et écran Fiche, ouvert depuis le bouton « Fiche complète » de chaque carte.
- Contenu : fil d'Ariane vers l'édition d'origine, bandeau score et thèmes, texte complet.
- Colonne Fiabilité : éditeur, statut de l'affirmation, élément de preuve (signalé comme écrit en anglais par l'IA), corroboration.
- Actions : article original, discussion, copier le lien. Liste des éditions qui ont publié la news.
- Sur petit écran, l'étiquette de fiabilité est affichée sous le titre.

**Correctif important** : la règle `lib/` du `.gitignore` excluait `frontend/src/lib`, donc le dépôt poussé ne compilait pas. La règle vise maintenant la racine seulement, et les fichiers sont versionnés.

---

## Lot 10 — Écran Préférences (version locale)

✅ Clôturé · Commit `efc5fbb` · Choix A : version locale, sans comptes.

**Fait**

- Écran Préférences :
  - liste des abonnés, ajout, suppression avec confirmation ;
  - réglages : langue, thèmes, sources, rythme, importance minimale, infos non confirmées, nombre maximum ;
  - barre d'enregistrement visible seulement s'il y a des changements ;
  - offre affichée, jamais modifiable.
- Protections de l'API qui écrit :
  - routes actives seulement en écoute locale ;
  - nom d'hôte local exigé (protection contre le DNS rebinding) ;
  - requêtes venant d'un autre site refusées ;
  - JSON seulement, 64 Ko maximum ;
  - identifiant opaque, jamais d'adresse e-mail dans les URL.
- Nouvelles dépendances : `radix-ui`, `react-hook-form`, `@hookform/resolvers`.

**Bug corrigé** : deux clics rapides sur deux thèmes n'en enregistraient qu'un.

---

## Lot 11 — Mesure de la qualité

🟡 Outil livré · Commit `337b0a2` · Étape 5 de la phase 2.

**Fait**

- Écran Qualité :
  - annotation **à l'aveugle** : aucun avis de l'IA affiché, ordre mélangé ;
  - 4 questions : place dans l'édition, importance, thèmes, statut de l'affirmation ;
  - résultats : sélection, importance, thèmes, affirmation, **faux fiables**.
- Commande `lucidnews-eval` :
  - mode gratuit, sur les analyses stockées ;
  - mode `--rerun`, avec les consignes actuelles (appels IA) ;
  - rapports enregistrés et écart avec la mesure précédente.
- Annotations dans `data/eval/annotations.json` (versionné). Rapports dans `data/eval/reports/` (non versionné).
- Méthode : [evaluation.md](evaluation.md).

**Reste** : les annotations humaines (lot 12). `--rerun` n'a pas encore été lancé avec la vraie clé.

---

## Lot 13 — Registre de confiance enrichi

✅ Clôturé · Étape 6 de la phase 2. Fait avant la fin du lot 12, car indépendant des annotations.

**Objectif** : mieux reconnaître qui publie, pour que l'étiquette de fiabilité soit juste.

**Fait**

| Sujet | Contenu |
|---|---|
| Comptes de réseaux sociaux | Un message est jugé sur **son compte**, pas sur la plateforme. Formats reconnus : X, Mastodon (tout le fédiverse), Bluesky, Telegram. Un compte enregistré l'emporte sur la plateforme. Deux comptes d'une même plateforme comptent comme deux éditeurs indépendants pour la corroboration. |
| Comptes intégrés | Seulement des comptes vérifiés à la main sur leur page publique : curl (Daniel Stenberg, Mastodon), Telegram (Pavel Durov), Bluesky (compte officiel). Aucun compte X : non vérifiable sans connexion. |
| Config | Nouveau réglage `reliability.accounts` (exemple : `"x:openai": "official"`), avec contrôle du format. |
| Autorités | Tout `gouv.fr`, CNIL, ARCEP ; tout `europa.eu` (déjà présent) ; BSI (Allemagne), NCSC (Pays-Bas), Garante (Italie), AEPD (Espagne). |
| Presse française | LeMagIT, JDN, L'Usine Digitale, Silicon, Siècle Digital, Clubic, Frandroid, Les Numériques, Les Échos, Le Figaro, Libération, franceinfo, AFP. |
| Presse européenne | heise, Golem, Euractiv, Politico Europe. |
| Recherche | Inria, CNRS. |
| Communautés françaises | LinuxFr, Developpez, Journal du hacker, Korben. |
| Sites repérés dans l'archive | Vérifiés puis ajoutés : pola.rs, gleam.run, reflection.ai, vals.ai (officiels) ; lucumr.pocoo.org, techdirt.com (reconnus). |
| Mesure de la qualité | L'étiquette de l'IA est recalculée avec le registre actuel : un changement de registre se voit sans relancer le pipeline. |

**Effet mesuré sur les 48 news de l'archive** (sans appel IA)

| Avant | Après |
|---|---|
| 4 Confirmé · 24 Fiable · 20 Non vérifié | 9 Confirmé · 21 Fiable · 18 Non vérifié |
| 20 éditeurs inconnus | 13 éditeurs inconnus |

- 8 news changent d'étiquette. Exemples : curl (Communautaire / Non vérifié → Officiel / Confirmé), Polars 2.0, Gleam et Reflection (Fiable → Confirmé).
- Aucune news ne descend.
- Les étiquettes déjà publiées ne sont pas réécrites. Le nouveau registre s'applique aux prochains runs.

---

## Lot 14 — Budget IA et quota épuisé

✅ Clôturé · Première moitié de la fin de la phase 2 (choix A). Le reste est au lot 14 bis.

**Objectif** : protéger le quota IA, réduire le coût de chaque run, et ne jamais bloquer l'application quand le quota est épuisé.

**Règle validée** : quand le quota est épuisé, l'application affiche les news **sans analyse IA**. Seulement dans ce cas : toute autre erreur d'analyse garde la news hors du digest, comme avant.

**Fait**

| Sujet | Contenu |
|---|---|
| Budget de tokens | Nouveau réglage `ai.max_tokens_per_run`. Une fois atteint, l'IA n'est plus appelée jusqu'à la fin du run. Valeur proposée dans la config d'exemple : 200 000 (un run de 24 h en consomme environ 140 000). |
| Quota du fournisseur | Reconnu à son message d'erreur : quota journalier Gemini, `insufficient_quota` (OpenAI), solde insuffisant (Anthropic, DeepSeek). Une limite **par minute** n'est pas un quota épuisé : elle reste retentée comme avant. |
| Pas de blocage | Dès que le quota est épuisé, chaque appel IA échoue tout de suite : plus d'attente, plus de nouvelle tentative, plus de pause de 30 s. Le run se termine normalement. |
| News non analysées | Marquées « non analysées » dans l'archive. Elles sont reprises au run suivant, sans consommer de tentative. Une news déjà analysée garde son analyse (sans enrichissement s'il n'était pas fait). |
| Publication à part | Jusqu'à 15 news non analysées (`digest.unanalyzed_max_items`, 0 pour aucune), dans une section « Sans analyse IA » : titre d'origine, source, lien. Toujours « Non vérifié », même d'une source officielle. Les sources les mieux connues passent en premier. |
| Digest et e-mail | Section dédiée avec un avertissement. Un abonné ne la reçoit que s'il ne filtre ni par catégorie ni par importance et accepte les infos non confirmées. |
| Interface | Bandeau dans l'édition (« Le quota IA a été épuisé pendant ce run »), section « Sans analyse IA » en fin d'édition et dans le sommaire, fiche d'une news avec un avertissement à la place du résumé, badge « Quota IA épuisé » dans les archives. |
| Suivi par run | L'archive garde, pour chaque run, la raison de l'arrêt de l'IA, les tokens utilisés et le nombre de news non analysées. |
| Réutilisation de l'enrichissement | Une news inchangée reprend aussi son enrichissement (titre traduit, résumé, contexte) s'il existe dans toutes les langues. Désactivable avec `archive.reuse_enrichment`. |

**Vérifié sur des runs simulés** (faux fournisseur IA, sans appel réel)

| Scénario | Résultat |
|---|---|
| Quota épuisé après 2 appels | Run terminé en moins d'une seconde, 3 appels IA au total. 5 news publiées « Sans analyse IA ». |
| Quota épuisé en cours de route | 4 news analysées dans le digest, 2 à part. |
| Budget de 1 500 tokens | Arrêt à 1 500 tokens, 3 news analysées, 3 à part. |
| Même lot de news au run suivant | Enrichissement repris : 19 appels IA → 1 seul. |

---

## Lot 14 bis — Corroboration élargie et qualité des sources

✅ Clôturé · Partie B du lot 14. Termine la phase 2 côté données (il reste les annotations du lot 12).

**Objectif** : mieux confirmer les news grâce à l'archive, et départager les news avec la fiabilité passée de leur source.

**Fait**

| Sujet | Contenu |
|---|---|
| Corroboration élargie | Une news retenue peut être confirmée par une news du même run restée **sous le seuil**, ou par une news de l'**archive** des 72 dernières heures. Ces « références » sont envoyées dans l'appel de dédoublonnage déjà existant : pas d'appel IA en plus, sauf pour une rubrique d'une seule news. |
| Garde-fous | Seules les références officielles ou reconnues sont envoyées (les autres ne comptent pas). 30 au plus par rubrique, les plus récentes d'abord. Une référence n'est jamais publiée ni retirée du digest. Une rumeur reste une rumeur. |
| Score de qualité par source | De 0 à 100, sur 30 jours : moitié score IA moyen, moitié part de news « Confirmé » ou « Fiable » (recalculée avec le registre actuel). Lissé vers 50 tant qu'une source a peu de news. |
| Usage du score | Il **départage seulement** deux news de même score IA (ordre du digest, choix de la news gardée lors d'un doublon, coupe aux quotas). Il ne fait jamais passer une news devant une news mieux notée. |
| Affichage du score | Nouvelle colonne « Qualité » dans `lucidnews-sources` et dans l'écran Sources, avec le détail au survol. |
| Recalcul de l'archive | Nouvelle commande `lucidnews-reassess` : aperçu par défaut, `--apply` pour écrire. Aucun appel IA. Les éditions passées affichent ensuite les étiquettes à jour. |
| Barre de navigation | Corrigé en passant : entre 768 et 1 024 px, la barre du haut débordait de l'écran. La barre du bas sert maintenant jusqu'à 1 024 px. |

**Mesuré sur une copie de l'archive** (48 news, sans appel IA)

| Mesure | Résultat |
|---|---|
| `lucidnews-reassess` | 4 Confirmé · 24 Fiable · 20 Non vérifié → 9 · 21 · 18. 6 news changent d'étiquette (curl, Polars 2.0, Gleam, Reflection…), 2 autres changent seulement de détail. Un second passage ne change plus rien. |
| Score de qualité | De 40 (Lobsters, 19 news, score moyen 3,4) à 61 (LWN, 4 news). Les sources sans news analysée n'ont pas de score. |

---

## Lot 15 — Cartes d'actualité interactives

✅ Clôturé · Premier lot du plan « interface complète ».

**Objectif** : chaque carte de l'édition s'ouvre au clic et montre l'essentiel, sans quitter l'édition.

**Fait**

| Sujet | Contenu |
|---|---|
| Ouverture | Clic n'importe où sur la carte, ou bouton « Détails ». Les liens (titre, source, discussion, fiche complète) gardent leur rôle. Une sélection de texte n'ouvre pas la carte. |
| Clavier | Bouton avec `aria-expanded` ; Échap referme la carte et rend le focus au bouton. |
| Carte fermée | Titre, source, date, domaines, résumé IA, étiquette de fiabilité (inchangé). |
| Carte ouverte | Blocs de l'IA (contexte, impact…), affirmation et preuve (marquée « en anglais »), fiabilité (éditeur, niveau, corroborations), tags, bouton « Lire l'article original ». |
| Données | Chargées au premier clic seulement, avec le même cache que la fiche complète : ouvrir la fiche ensuite ne refait pas la requête. Si l'API renvoie une autre news que celle de la carte, rien n'est affiché. |
| États | Chargement (zones animées), erreur avec « Réessayer », résumé IA absent (« Pas encore de résumé IA pour cette news »). |

**Vérifié** : 5 nouveaux tests d'interface (25 au total), build, rendu dans le navigateur sur ordinateur et téléphone, sans défilement horizontal.

---

## Lot 16 — Socle de pilotage et page Réglages

✅ Clôturé · Décision : clés dans le fichier `.env` du projet.

**Objectif** : modifier la configuration et les clés API depuis l'interface, de façon sûre.

**Fait**

| Sujet | Contenu |
|---|---|
| Page Réglages | Nouvelle entrée de navigation. Sections IA, Collecte, Sélection (seuil et fusion par rubrique, news par édition, news sans analyse), Fiabilité, Archive. Barre d'enregistrement flottante, erreurs sous chaque champ. |
| Clés API | Liste des variables que la config utilise, avec leur état : enregistrée dans `.env`, définie dans le terminal (prioritaire), absente. Saisie masquée, remplacement, suppression avec confirmation. La valeur n'est jamais renvoyée ni affichée. |
| Écriture de la config | Lecture brute du fichier ; seuls les champs modifiés sont écrits ; les `${VARIABLE}` sont conservés et les champs qui en contiennent sont verrouillés ; validation par le modèle `Config` ; écriture atomique. |
| Sauvegardes | Copie horodatée avant chaque écriture dans `data/backups/` (ignoré par Git), 10 gardées, restauration depuis l'écran. |
| Conflits | Si le fichier a changé depuis sa lecture, l'écriture est refusée et l'écran propose de recharger. |
| Sécurité | Routes locales seulement (adresse, Host, Origin vérifiés). Clés en droits `600`. Une clé collée dans le champ « Variable de la clé » est refusée sans être répétée. Aucune clé dans les journaux. |
| Rechargement | L'API sert la nouvelle config tout de suite (langues, sources, profils) ; le pipeline la lit au run suivant. |
| Navigation mobile | Six entrées : libellé court « Abonnés » pour Préférences dans la barre du bas, police ajustée. Testé à 360 px en français et en anglais. |

**Vérifié** : 24 tests Python (682 au total), 7 tests d'interface (32 au total), build. Dans le navigateur, sur une copie de la config : un enregistrement ne change que la section modifiée, la restauration rend le fichier identique, aucune clé dans les journaux.

---

## Lot 17 — Gestion des sources

✅ Clôturé · Décision : X (Twitter) en lecture seule.

**Objectif** : gérer les sources depuis l'interface, avec leur état réel.

**Fait**

| Sujet | Contenu |
|---|---|
| Liste | Page Sources : sous la santé, les sources configurées par groupe (flux RSS, GitHub, Reddit, Telegram, sources intégrées, X). Filtre Toutes / Actives / Désactivées / À vérifier. |
| État affiché | Santé des runs passés quand elle existe ; sinon « Pas encore collectée », « Désactivée », « En pause » (interrupteur Reddit ou Telegram coupé), « Comptée avec ses subreddits » (compte Reddit), « Lecture seule » (X). Rien n'est inventé. |
| Actions | Interrupteur par source et par groupe. Panneau latéral : ajouter (flux RSS, dépôt ou compte GitHub, subreddit, compte Reddit, chaîne Telegram), modifier, tester, supprimer avec confirmation. Sources intégrées : activer et régler, pas supprimer. |
| Saisie | Liens collés acceptés (`r/rust`, `@chaine`, `https://t.me/s/…`, URL GitHub). Doublons refusés (même nom ou même flux, sans tenir compte des majuscules). Limites vérifiées par l'interface puis par l'API. |
| Test | Le vrai collecteur, sur 7 jours, 45 s au plus, sans IA ni archive : nombre de contenus, part dans la fenêtre de collecte, 5 derniers titres, ou l'erreur exacte (y compris celles que le collecteur ne fait que journaliser). |
| Écriture | Même socle que le lot 16 : config brute, seuls les champs changés, copie de sauvegarde, version vérifiée. Une source qui contient une `${VARIABLE}` est verrouillée (activable, pas modifiable). L'API recharge la santé tout de suite ; le run suivant collecte la source. |
| Sécurité | Routes locales seulement. Adresse de flux publique obligatoire (`localhost`, adresses privées, `file:` et `${VARIABLE}` refusés). Pendant un test, chaque requête et chaque redirection est vérifiée. Un jeton d'une `${VARIABLE}` n'apparaît jamais dans la réponse. |

**Vérifié** : 37 tests Python (719 au total), 8 tests d'interface (40 au total), build. Tests réels sur le réseau : LWN, Simon Willison, vllm, r/rust, Hacker News et une chaîne Telegram répondent ; une page 404 donne son erreur ; `192.168.1.1` et `127.0.0.1` sont refusées. Dans le navigateur, sur une copie de la config : ajout puis suppression rendent un fichier identique à l'original ; affichage vérifié sur ordinateur et à 375 px.

---

## Lot 18 — Domaines surveillés et couverture

✅ Clôturé · Décisions : les 12 catégories existantes ; lacune sous 2 sources actives ou 3 news sur la période.

**Objectif** : choisir les domaines suivis et savoir si les sources les couvrent assez.

**Fait**

| Sujet | Contenu |
|---|---|
| Onglet Domaines | Page Sources, nouvel onglet (gardé dans l'adresse). Chiffres clés : domaines suivis, bien couverts, lacunes, news analysées. Une carte par catégorie. |
| Couverture | Calculée seulement sur l'archive de la période : news analysées et publiées, sources actives qui ont alimenté le domaine, dernière news, part confirmée ou fiable (registre actuel). Une source qui n'est plus configurée reste visible, barrée. Les news sans analyse IA ou sans catégorie ne sont pas comptées, et leur nombre est affiché. |
| Lacunes | Domaine suivi sous l'un des deux seuils, avec la raison (« Moins de 2 sources actives », « Moins de 3 news en 14 jours »). Seuils réglables dans l'onglet. Un domaine non suivi n'est jamais une lacune. |
| Recommandations | Catalogue livré avec le projet : flux de la config d'exemple et catalogue de l'assistant, rattachés aux 12 catégories (55 sources ; flux à clé et WeChat écartés). Seules les sources absentes de la config sont proposées (par clé et par adresse de flux), avec le badge « Recommandée · non configurée ». Ajout avec l'outil du lot 17, après un test. |
| Domaines suivis | Interrupteur par domaine. Option « Ne publier que les domaines suivis » : appliquée réellement par la sélection du digest (même règle pour le pipeline et le MCP). Elle demande au moins un domaine suivi. |
| Réglages | `digest.watched_categories`, `only_watched_categories`, `coverage_min_sources`, `coverage_min_items`, enregistrés par la route des réglages (config brute, sauvegarde, version). |
| Sans API locale | Couverture et recommandations lisibles, aucune modification possible (message affiché). |

**Vérifié** : 9 tests Python (728 au total), 6 tests d'interface (46 au total), build. Sur une copie de tes données : 5 lacunes réelles (Cloud, DevOps, Data, Bases de données, Technologies émergentes) ; ajout de « PostgreSQL News » depuis la carte Bases de données après un test (7 contenus sur 7 jours) ; seuls les champs cliqués écrits dans le fichier ; avec seulement Cybersécurité suivie, la sélection garde 3 news sur 14 dans l'archive. Affichage vérifié sur ordinateur et à 375 px. Réponses de l'API en moins de 10 ms.

---

## Lot 19 — Qualité de la veille

✅ Clôturé · Décision : les compteurs de doublons commencent au premier run après ce lot, sans reconstitution du passé.

**Objectif** : savoir, sur une seule page, si la veille est pertinente et fiable.

**Fait**

| Sujet | Contenu |
|---|---|
| Page | Qualité, nouvel onglet « Vue d'ensemble » en premier (`/quality`) ; Annoter passe à `/quality/annotate`, Résultats reste à `/quality/results`. Période 7, 14 ou 30 jours. |
| Chiffres clés | Lacunes sur les domaines suivis, sources actives sur configurées, âge médian des news publiées, part confirmée ou fiable. |
| Cartes | Couverture (lot 18) ; diversité (sources actives, sources publiées, part de la première source collectée et publiée) ; santé (statuts, sources jamais collectées, 5 dernières erreurs) ; fraîcheur (médiane, 90e centile, part sous 24 h) ; doublons et filtrage (entonnoir collectés → fusionnés par URL → au-dessus du seuil → fusionnés par sujet → publiés, avec un texte lisible par les lecteurs d'écran) ; qualité du filtrage (annotations, « échantillon insuffisant » sous 30) ; fiabilité publiée (répartition, news sans analyse IA). |
| Honnêteté des chiffres | Chaque carte indique sa source et sa période. Un run sans compteur est compté à part (« pas de donnée »). Une période vide affiche « Pas de donnée », jamais zéro inventé. Les annotations ne sont résumées qu'avec l'API locale. |
| Archive | Schéma 5 : `url_merged_count`, `topic_merged_count`, `above_threshold_count` par run, vides pour les runs anciens. Le pipeline les enregistre après la sélection (zéro pour un run sans contenu). La migration est automatique à la prochaine ouverture. |
| API | `GET /api/quality/overview?days=` (1 à 90 jours). |

**Vérifié** : 7 tests Python (735 au total), 6 tests d'interface (52 au total), build. Sur une copie de tes données : 8 runs, tous antérieurs aux compteurs, donc « pas de donnée » pour les doublons ; 5 lacunes, 11 sources actives sur 29, âge médian 4,1 h, 13 news confirmées ou fiables sur 14 ; aucune annotation. Entonnoir vérifié en ajoutant des compteurs au dernier run de la copie (affichage seulement). Ordinateur et 375 px. Réponse de l'API en 30 ms.

---

## Lot 20 — Lancer et planifier les runs

✅ Clôturé · Décision : planification par une tâche launchd générée par l'interface. Deux vérifications réelles attendent ton accord (voir « Blocages »).

**Objectif** : générer une édition depuis l'interface et régler sa fréquence.

**Fait**

| Sujet | Contenu |
|---|---|
| Lancer | Réglages, nouvelle section « Runs » en tête. Le bouton lance le pipeline dans un processus séparé, avec la même commande qu'en terminal. Journal dans `data/runs/`. |
| Un seul run | Verrou `data/run.lock` (flock) tenu par le pipeline pendant tout le run, quelle que soit l'origine. Second lancement refusé : 409 dans l'interface, code 75 en terminal. Un run planté ne bloque pas le suivant. |
| Suivi | Étapes (collecte, analyse IA, sélection, édition, fini) lues dans la vraie sortie (un traceback qui cite le code ne compte pas). Dernières lignes du journal sans couleurs ni valeur de clé, affichées depuis la fin. Échec affiché avec son code ; journal ouvert. Rafraîchi toutes les 2 s pendant un run, même onglet en arrière-plan. |
| Planification | Activer, heure, jours (aucun = tous les jours), prochain run calculé. Tâche launchd écrite de façon atomique, rechargée, retirée à la désactivation ; refus de launchd affiché, rien n'est laissé. Aucune clé dans la tâche. macOS seulement (message ailleurs). |
| Historique | 20 derniers runs de l'archive, statut réel, erreur, lien vers l'édition publiée. |
| Sécurité | Routes locales seulement. Journal nettoyé des valeurs de clés (variables déclarées par la config, terminal et `.env`). |

**Vérifié** : 20 tests Python (755 au total) avec un faux pipeline et un faux `launchctl` (aucun appel IA, aucune tâche chargée), dont un `plutil -lint` de la tâche générée ; 6 tests d'interface (58 au total) ; build. Démo réelle sur une copie des données, sans clé IA et sans envoi possible : le run part depuis l'interface, la collecte se fait (31 contenus), l'échec « clé manquante » s'affiche avec son code et son journal ; un second lancement est refusé (409) et un lancement en terminal pendant ce temps aussi (code 75) ; aucune valeur de clé dans les journaux. Téléphone 375 px.

**Vérifié** : une vraie tâche launchd se déclenche à l'heure prévue et le run aboutit (copie des données, IA désactivée). **Pas encore vérifié** : un vrai run avec l'IA lancé depuis l'interface (accord demandé).

**Corrigé pendant les essais** : étape fausse quand un traceback citait le code ; page élargie à 776 px sur téléphone par les longues lignes du journal ; suivi figé quand l'onglet est en arrière-plan.

## Lot 21 — Newsletter : contenu et préférences

✅ Clôturé · Décisions : « complet » = le rendu actuel (aucun changement pour les abonnés existants) ; envoi hebdomadaire au premier run du jour choisi dans la config.

**Objectif** : une newsletter qui suit réellement les préférences de chaque abonné.

**Fait**

| Sujet | Contenu |
|---|---|
| Niveau de détail | Préférence `detail_level` : « bref » (titre, fiabilité, résumé, source) ou « complet » (en plus : contexte, références, tags de l'enrichissement). Défaut « complet » : un `subscribers.json` ancien se charge sans changement. Réutilise les textes déjà produits : aucun appel IA. Deux niveaux = deux rendus distincts. |
| Envoi hebdomadaire | Les abonnés « hebdomadaire » reçoivent les meilleures news publiées des 7 derniers jours (archive, `items_between`), le jour `email.weekly_day` (0 = lundi) au premier run de la journée, au plus une fois par semaine ISO (`data/weekly_sent.json`). Plafond `email.weekly_max_items` (15), ou le `max_items` de l'abonné s'il est plus bas. Ni news non analysées, ni e-mail vide. Déclenché aussi quand le run du jour ne trouve rien de nouveau. |
| E-mail refait | Un seul rendu pour l'envoi et l'aperçu (`render_email`) : mise en page aux couleurs de l'application, citation d'introduction et sommaire corrects, aucun script, aucune image distante, aucun formulaire. Le texte des sources n'est plus échappé deux fois (un `&` ou un `<` s'affichait `&amp;`). |
| Aperçu | Préférences : « Voir l'aperçu » construit l'e-mail du lecteur depuis l'archive avec ses préférences enregistrées (`GET /api/subscribers/<id>/preview`), dans un cadre `iframe` sans script. Quotidien : dernière édition publiée. Hebdomadaire : les 7 derniers jours. Dit quand il n'y a pas d'édition, quand rien ne serait envoyé et quand la langue demandée n'existe pas. |
| Même code | L'aperçu passe par `plan_deliveries` et `render_selection`, comme l'envoi : un test compare le HTML, le texte et l'objet de l'e-mail envoyé à ceux de l'aperçu. |

**Vérifié** : 13 nouveaux tests Python (768 au total) : niveaux de détail, valeur par défaut et ancien `subscribers.json`, envoi hebdomadaire (fenêtre de 7 jours, plafond, une fois par semaine, jour d'envoi), aperçu identique à l'e-mail envoyé, HTML de source échappé, route locale seulement ; 5 nouveaux tests d'interface (63 au total) ; build. Démo réelle sur une copie des données : aperçu quotidien « bref » 4 175 caractères contre « complet » 6 825, aperçu hebdomadaire de 14 news (5 au 11 octobre), cadre sans `allow-scripts`, téléphone 375 px sans défilement horizontal. Aucun e-mail réel envoyé.

**Pas encore vérifié** : un envoi SMTP réel (aucun compte configuré) ; l'ordre des news de l'aperçu quotidien vient de l'archive (score), celui de l'envoi du run en cours peut différer légèrement (équilibrage entre groupes).

**Ajout hors plan (demande du 11 octobre)** : filtre de date sur la page Édition. Voir « Filtre de date de l'Édition » plus bas.

**Corrigé pendant les essais** : citation d'introduction affichée en texte brut (`> Sur 46…`) et sommaire collé en un paragraphe ; double échappement des textes de sources ; titre de l'aperçu écrasé sur téléphone.

---

### Filtres de l'Édition et sources par domaine

Demandes hors plan, faites après le lot 21.

| Sujet | Contenu |
|---|---|
| Filtre de date | Page Édition, barre « Filtrer par date » : Dernière édition, Jour, Mois, Année. Jour : calendrier (jours avec édition seulement). Mois et Année : périodes qui ont une édition. La période est dans l'adresse (`?day=`, `?month=`, `?year=`) : partageable, Retour marche, valeur invalide ignorée. |
| Résultat d'une période | Toutes les éditions commencées dans la période, fusionnées : une news publiée par plusieurs éditions apparaît une fois ; rubriques et tri par score comme une édition. **Aucune limite** sur le nombre de news affichées. Le chiffre « contenus analysés » n'est pas montré (une même news serait comptée par chaque édition). |
| Filtre de domaine | À côté du filtre de date, sur la dernière édition comme sur une période : « Tous les domaines » ou l'un des 12 domaines, avec le nombre de news de chacun dans ce qui est affiché (domaine à 0 grisé). Adresse `?domain=ai`. Les news sans analyse IA n'ont pas de domaine : masquées tant qu'un domaine est choisi, et la page le dit. |
| Sources par domaine | Sources › Sources configurées : regroupées par domaine (ou par type, au choix), le domaine de chaque source est affiché sur sa ligne avec son origine. Domaine = catégorie la plus fréquente des news analysées de la source (90 jours), « d'après N news analysées », avec les autres domaines ; sans news analysée : catégorie du catalogue (« selon le catalogue ») ; sinon « pas encore déterminé », jamais deviné. Les interrupteurs Reddit et Telegram restent dans une section à part. |
| API | `GET /api/editions/period?since=&until=&lang=` (instants ISO, bornes locales, fin exclue, 3 700 jours au plus) ; `GET /api/editions?limit=` (jusqu'à 2000) ; `GET /api/sources/domains?days=90`. |
| Vérifié | 772 tests Python, 72 tests d'interface, build. Archive réelle (copie) : octobre = 9 éditions et 20 news ; sur 44 sources listées, 21 ont un domaine (archive ou catalogue), 23 « pas encore déterminé ». |
| Observé, non corrigé | À 1024 px de large, l'en-tête (groupe langue/éclair à droite) dépasse de 30 px la fenêtre : défaut de l'en-tête, antérieur à ces changements. |

## Lot 22 — Newsletter : envoi fiable

✅ Clôturé (sauf le fuseau horaire, reporté) · Décisions : liens servis par un service public séparé (A) ; Resend comme fournisseur d'API, SMTP conservé ; abonnés en base SQLite.

**Objectif** : des envois sûrs, traçables et conformes.

**Fait**

| Sujet | Contenu |
|---|---|
| Double confirmation | Un lecteur ajouté (Préférences ou e-mail `SUBSCRIBE`) est « en attente » et reçoit un lien. **Aucun digest avant confirmation** : le plan d'envoi filtre, et l'envoi revérifie chaque adresse. Ouvrir le lien ne change rien (anti-scanners) ; le bouton confirme. |
| Liens signés | Jeton HMAC-SHA256 (`NEWSLETTER_SIGNING_KEY`, ≥ 16 caractères, dans `.env`). Confirmation valable 7 jours, désinscription sans expiration. Jeton modifié, expiré, d'une autre action ou d'une autre clé : refusé. Chaque e-mail porte le lien de désinscription de son lecteur et les en-têtes `List-Unsubscribe` / `List-Unsubscribe-Post` (un clic). |
| Service public | `lucidnews-public` : processus séparé, 4 routes + `/health`, rien d'autre ; ne journalise jamais le jeton ; même base que le pipeline (doit tourner où est `data/`). |
| Fournisseur | `email.provider` : `smtp` ou `resend` (API HTTPS, clé jamais exposée, erreurs sans clé). Avec Resend, pas de digest sans lien de désinscription. |
| Abonnés en base | `data/newsletter.sqlite3` (`subscribers`, `deliveries`). `subscribers.json` importé une fois, **comme confirmé** (ils recevaient déjà, pas de preuve de consentement), puis renommé `.migrated`. Supprimer un lecteur efface sa ligne et son journal ; se désinscrire garde l'adresse seule (suppression). |
| Journal des envois | Chaque envoi (confirmation, quotidien, hebdomadaire) : lecteur, date, objet, édition ou semaine, résultat, erreur. Préférences : journal du lecteur choisi, ou de tous. Une semaine entièrement ratée reste « à envoyer ». |
| Interface | Préférences : statut de chaque lecteur (en attente, confirmé, désinscrit, avec icône et texte), bandeau d'explication, « Envoyer le lien de confirmation », résultat du premier envoi du lien, journal. |
| API | `POST /api/subscribers` (en attente + lien), `POST /api/subscribers/<id>/confirmation`, `GET /api/deliveries`, `GET /api/subscribers/<id>/deliveries` (locales). Secrets déclarés dans Réglages › Clés API. |

**Vérifié** : 25 nouveaux tests Python (797 au total : jetons valides, expirés, falsifiés ; migration JSON vers base ; transitions de statut ; rien avant confirmation ; lien propre à chaque lecteur ; journal d'un envoi en échec ; Resend et SMTP avec transports simulés ; service public sur un vrai serveur local), 9 nouveaux tests d'interface (77 au total) ; build. Démo sur une copie, sans aucun envoi possible (SMTP vers un port fermé) : migration de 2 lecteurs, ajout en attente, échec journalisé, lien ouvert sans effet, jeton modifié refusé (400), bouton confirme, désinscription en un clic, routes de l'API absentes du service public (404), aucun jeton dans le journal du service. Téléphone 375 px.

**Reporté** : envoi selon le fuseau horaire du lecteur. L'appliquer vraiment demande un envoi différé à l'heure locale de chaque lecteur, donc une tâche d'envoi qui tourne souvent, en plus de la planification quotidienne du lot 20. Un champ de fuseau sans cela serait un paramètre qui ne s'applique pas. À décider (voir « Blocages »).

**Pas encore vérifié** : un envoi réel avec Resend (aucune clé configurée), et le service public derrière un vrai HTTPS.

---

## Lot 23 — Recherche dans l'archive

✅ Clôturé · Décision : l'index porte sur le texte déjà produit (titres, résumés, tags, contexte), pas sur le corps brut des articles.

**Objectif** : retrouver une news passée par mot-clé, domaine, source ou fiabilité.

**Fait**

| Sujet | Contenu |
|---|---|
| Index | Table FTS5 `items_fts` dans l'archive (schéma 6), alimentée à chaque enregistrement de news. Indexé : titre original et titres localisés, résumé IA, tags, auteur, texte de tous les blocs d'enrichissement (toutes les langues). Pas le corps brut des articles (long et bruyant). Seules les news analysées sont indexées (les autres n'ont pas de page). |
| Archive existante | Indexée automatiquement à la première ouverture (81 news de ton archive en moins de 0,2 s) ; une seule fois. Sans FTS5 dans SQLite : l'archive marche, la recherche répond « indisponible » (503) et l'interface l'explique. |
| Requête | Coupée en mots simples, chacun entre guillemets et en préfixe : accents et majuscules ignorés (`ecosysteme` trouve `écosystème`, `kuber` trouve `Kubernetes`), tous les mots requis. Les opérateurs tapés (`OR`, `NEAR`, `*`, guillemets, `title:`, SQL) sont des mots, jamais des commandes. Vide, 1 lettre, plus de 200 caractères ou plus de 10 mots : refusé proprement (400). |
| API | `GET /api/search?q=&category=&source=&label=&limit=&offset=&lang=` : résultats avec titre et résumé dans la langue, score, fiabilité, domaines, source, date, édition qui l'a publiée (ou « jamais publiée »), compteurs pour les filtres. `truncated` si plus de 1 000 correspondances (seules les meilleures sont prises en compte, et l'interface le dit). |
| Interface | Archives : champ de recherche en tête ; filtres Domaine, Fiabilité, Source avec leur nombre de résultats ; mots trouvés surlignés (même règle que la recherche) ; pagination de 30 ; chaque résultat ouvre la fiche de la news, avec retour à son édition. Tout est dans l'adresse (`?q=&category=&label=&source=&offset=`). Sans recherche, la page est inchangée (calendrier et éditions). |

**Vérifié** : 18 tests Python (815 au total : requêtes hostiles, accents et préfixes, mise à jour de l'index, indexation d'une archive existante, filtres et compteurs, pagination, erreurs 400 et 503), 8 tests d'interface (85 au total) ; build. Archive réelle (copie) : « polars » 2 résultats, « sécurité » 3, « kuber » 0 (aucune news sur le sujet), requête SQL hostile sans effet ; réponse en 11 ms. Téléphone 375 px.

---

---

# Lots suivants

Plan revu le 9 octobre 2026 pour intégrer le besoin « interface complète et gestion du produit » : piloter LucidNews depuis l'interface, sans terminal pour les opérations courantes. Les anciens lots 15 à 18 sont repris et renumérotés selon le nouvel ordre (voir la correspondance plus bas).

## Ordre d'exécution et dépendances

| Ordre | Lot | Dépend de | Pourquoi à cette place |
|---|---|---|---|
| ✅ | 15 — Cartes d'actualité interactives | — | Clôturé. |
| ✅ | 16 — Socle de pilotage et Réglages | — | Clôturé. |
| ✅ | 17 — Gestion des sources | 16 | Clôturé. |
| ✅ | 18 — Domaines surveillés et couverture | 16, 17 | Clôturé. |
| ✅ | 19 — Qualité de la veille | 18 (couverture), 12 (filtrage) | Clôturé. |
| ✅ | 20 — Lancer et planifier les runs | 16 | Clôturé (deux vérifications réelles en attente d'accord). |
| ✅ | 21 — Newsletter : contenu et préférences | 20 (fréquence) | Clôturé. |
| ✅ | 22 — Newsletter : envoi fiable | 21 | Clôturé (fuseau horaire reporté). |
| ✅ | 23 — Recherche dans l'archive | — | Clôturé. |
| ✅ | 24 — Finitions de l'interface | 15 à 23 | Clôturé. |
| ✅ | 25 — Dette technique | — | Clôturé. |
| ✅ | 25 bis — IA facultative | — | Clôturé. |
| 🟡 | 26 — Comptes et SaaS | 22, 25 | Authentification faite ; rôles → lot 27, offres et paiement → lot 42. |
| 1 | 27 à 46 — Plan de lancement | 26 | Voir [Plan.md](../Plan.md). |
| En parallèle | 12 — Annoter au moins 30 news | — | Action humaine ; donne les chiffres de filtrage du lot 19. |

**Correspondance avec l'ancien plan** : ancien 15 (finitions) → 24 · ancien 16 (newsletter) → 21 et 22 · ancien 17 (comptes et SaaS) → 26 · ancien 18 (dette technique) → 25.

## Navigation visée

On garde les écrans existants et on n'ajoute qu'**une** page : Réglages.

| Page | Contenu après le plan |
|---|---|
| Édition | Édition du jour, cartes interactives (lot 15). |
| Archives | Éditions passées, recherche (lot 23). |
| Sources | Onglet « Sources » : santé et gestion (lot 17). Onglet « Domaines » : domaines suivis, couverture, recommandations (lot 18). |
| Qualité | Onglet « Vue d'ensemble » : indicateurs de la veille (lot 19). Onglets « Annoter » et « Résultats » : existants. |
| Préférences | Préférences des abonnés (existant), niveau de détail et aperçu de la newsletter (lot 21). |
| Réglages (nouvelle) | Clés API, IA, collecte et traitement (lot 16), lancement et planification des runs (lot 20). |

## Lot 12 — Annoter au moins 30 news

🟡 Action humaine · Prérequis à toute conclusion sur la qualité du filtrage.

- Annoter au moins 30 news dans l'écran Qualité, en mélangeant retenues et écartées. L'archive en contient 48.
- Remplir le champ Notes en cas d'hésitation.
- Lancer `uv run lucidnews-eval` pour obtenir la mesure de départ, puis `--rerun` une fois comme référence.

---

## Lot 24 — Finitions de l'interface

✅ Clôturé. Ancien lot 15.

- **Objectif** : finir le rendu premium sur toutes les pages, y compris les nouvelles.
- **Réalisé** :
  - **Mode sombre** : clair par défaut, bouton soleil/lune dans la barre du haut, choix gardé dans le navigateur (`lucidnews.theme`) et appliqué avant le premier affichage (pas de flash). Mêmes jetons de couleur, redéfinis sous `html[data-theme='dark']`. Un jeton `on-fill` donne le texte posé sur un fond plein (blanc en clair, sombre en sombre).
  - **Contrastes AA** : `src/design/contrast.test.ts` lit les couleurs dans `styles.css` et vérifie 26 paires par thème (texte 4,5 : 1 ; graphiques et focus 3 : 1). Il a révélé trois couleurs claires sous le seuil, corrigées : texte discret, « non vérifié » et série « collectées ».
  - **Socle allégé** : le moteur d'animation est chargé après le premier affichage (`LazyMotion`). Noyau JS : 184,8 Ko → 146,1 Ko compressés (−21 %).
  - **Lint et format** : `oxlint` (0 erreur, 3 avertissements voulus : formulaires qui suivent les données du serveur) et `prettier` (largeur 160). Scripts `npm run lint`, `format`, `format:check`. `eslint` n'est pas utilisé : `typescript-eslint` n'accepte pas encore TypeScript 7.
  - **Barre du haut** : le menu reste en haut dès 1024 px ; espaces resserrés entre 1024 et 1279 px pour que le bouton de thème tienne sans débordement.
- **Pages** : toutes.
- **Backend** : aucun.
- **Critères de validation** : chaque page lisible dans les deux thèmes (contrôlées une à une dans le navigateur) ; aucune erreur de lint ; poids du socle mesuré avant et après.
- **Tests** : 140 tests interface (dont 53 de contraste et 2 de bascule du thème).
- **Non couvert** : l'aperçu de la newsletter reste volontairement sur fond blanc (c'est le rendu réel de l'e-mail) ; le thème ne suit pas le réglage du système (choix B).

## Lot 25 — Dette technique

✅ Clôturé. Ancien lot 18.

- **Paquet renommé** : `src` → `lucidnews` (dossier, imports, points d'entrée `uv run lucidnews-*`, `python -m lucidnews.main`, Dockerfile, documentation). Le paquet construit embarque toujours les profils intégrés (vérifié sur la roue).
- **Orchestrateur découpé** : `orchestrator.py` passe de 1 620 à 784 lignes. Les étapes vivent dans `lucidnews/pipeline/` : `collect.py` (collecte des sources, fusion des doublons entre sources), `select.py` (seuil, filtre de profil, digest équilibré, news non analysées), `deliver.py` (newsletters et texte du digest). `PipelineOrchestrator` les assemble : mêmes méthodes, même comportement.
- **Défaut corrigé** : fusionner deux sources sur une même URL ne recopie plus le nom de flux, le dépôt, le sous-reddit, etc. de l'autre source. Une news Hacker News ne s'affiche plus avec « Lobsters ». Les chiffres d'engagement (commentaires, score) restent combinés.
- **Tests** : 816 (un ajouté pour le défaut). Seul changement dans les tests existants : les noms `src.` deviennent `lucidnews.`, et les doubles de scrapers visent `lucidnews.pipeline.collect` là où le code est maintenant.
- **Non fait** : `ruff` signale 25 avertissements anciens (non liés) ; aucun outil de format Python n'est imposé par le projet.

---

## Lot 25 bis — IA facultative et clés hors de l'interface

✅ Clôturé. Demande : projet open source, application utilisable sans IA, aucune clé saisie dans l'interface.

- **Clés** : la saisie de clés API est supprimée de l'interface (lot 16). Plus aucune route n'écrit ou supprime une clé : `PUT` et `DELETE /api/secrets/<nom>` répondent 405. `GET /api/secrets` reste, en lecture seule : il dit si la variable est définie, jamais sa valeur. Les clés se fournissent hors de l'interface : `.env`, terminal, secret GitHub (Codespaces, Actions). Documenté dans le README, section « Activer l'analyse IA (facultatif) ».
- **Case à cocher** « Activer l'analyse par IA » dans Réglages (`ai.enabled`). **Désactivée par défaut** pour une nouvelle configuration. Désactivée : aucun client d'IA n'est créé, aucune clé n'est nécessaire, rien n'est envoyé à un fournisseur ; ni déduplication par sujet, ni enrichissement, ni relecture des réponses X n'appellent l'IA. Le run collecte, fusionne les doublons, applique la fiabilité de l'éditeur et liste les news **sans analyse** (même mécanisme que le quota épuisé, nouvelle raison `disabled`). Les analyses déjà en archive restent réutilisées.
- **IA activée mais sans clé** : le run ne plante plus. Un avertissement est affiché et le run continue comme « désactivée ».
- **Interface** : les champs fournisseur, modèle et limites ne s'affichent que si l'IA est activée, avec l'état de la clé (détectée ou non). Les textes « quota épuisé » deviennent « sans analyse IA » quand la raison peut être l'une ou l'autre.
- **Assistant** (`lucidnews-wizard`) : active l'IA, puisque l'utilisateur vient de choisir un fournisseur.
- **Vérifié** : run réel sur une copie des données, IA désactivée alors qu'une clé existait dans `.env` : 0 token, 42 news listées sans analyse, run en succès, `ai_limit = disabled`. Même run déclenché par une vraie tâche launchd (voir Blocages).
- **À savoir** : une configuration existante sans `ai.enabled` passe à « désactivée » ; il suffit de cocher la case.
- **Défaut du lot 25 corrigé au passage** : un import différé dans `pipeline/collect.py` pointait au mauvais endroit (la collecte échouait dès la première exécution réelle) et une variable `src` avait été renommée par erreur dans `setup/presets.py`. Ajout de `tests/test_package_layout.py` (import de chaque module, résolution de chaque import relatif).
- **Tests** : 819 Python, 142 interface.

---

## Lot 26 — Comptes et SaaS (phase 4)

🟡 Commencé : l'authentification est faite (demande explicite). Rôles, limites d'offre et paiement restent non commencés.

**Réalisé : authentification facultative** (`auth.enabled`, désactivée par défaut : l'application reste ouverte).

- **Inscription et connexion par e-mail et mot de passe**, sans vérification d'e-mail. Mots de passe hachés avec scrypt (sel aléatoire), 8 à 128 caractères. Réponse identique pour « adresse inconnue » et « mauvais mot de passe », avec un temps de calcul identique. Limitation des tentatives (8 par adresse et 20 par IP par 15 min ; 10 inscriptions par IP et par heure).
- **Connexion Google réelle (OAuth 2.0)** : flux « code d'autorisation » avec PKCE, `state` à usage unique lié au navigateur par un cookie, `nonce`, adresse vérifiée par Google exigée. Le bouton n'apparaît que si `GOOGLE_CLIENT_ID` et `GOOGLE_CLIENT_SECRET` sont définis. Procédure Google Cloud : README.
- **Session persistante** côté serveur : cookie aléatoire `HttpOnly`, `SameSite=Lax`, `Secure` si `public_url` est en https ; seul son SHA-256 est stocké ; 30 jours glissants. **Déconnexion** qui invalide la session côté serveur (un cookie volé avant ne marche plus).
- **Routes privées** : avec les comptes, toute l'API sauf `/api/auth/*` répond 401 sans session ; l'interface renvoie vers `/sign-in?next=…` et revient à la page demandée, y compris quand une session se termine pendant l'usage.
- **Interface** : page `/sign-in` et `/sign-up` (panneau de marque avec exemples d'étiquettes de fiabilité, bascule animée entre les deux onglets, indicateur de solidité du mot de passe, états de chargement et de réussite, messages d'erreur précis, FR/EN, thème clair et sombre) ; avatar et déconnexion dans la barre du haut. Sur téléphone, le nom « LucidNews » cède la place au logo seul quand un compte est connecté, pour que le bouton du compte tienne.
- **Sans vérification d'e-mail, deux conséquences traitées** : une adresse inscrite avec mot de passe devenant ensuite un compte Google perd son mot de passe et ses autres sessions (sinon la personne inscrite en premier avec l'adresse d'un autre garderait l'accès) ; l'inscription révèle si une adresse est déjà utilisée.
- **Vérifié** : inscription, connexion persistante après rechargement, déconnexion, et page de connexion sur téléphone (375 px) en clair et en sombre, sur une copie des données, avec le vrai serveur. L'adresse de redirection Google construite est la bonne (`http://localhost:5173/api/auth/google/callback`).
- **Pas vérifié** : un vrai aller-retour avec Google (aucun identifiant client dans cet environnement). Le flux est testé contre un faux point d'accès « token » local qui répond comme Google ; le code appelé est le vrai.
- **Inscriptions fermées** (`auth.allow_signup: false`) : la page d'inscription le dit et son bouton est désactivé ; le serveur refuse aussi l'inscription par e-mail et par Google pour une nouvelle adresse. Les comptes se gèrent alors en terminal avec `lucidnews-users` (`add`, `list`, `passwd`, `remove` ; mot de passe lu sans écho, jamais en argument).
- **Tests** : 37 Python (`tests/test_auth.py`), 10 interface (`AuthPage.test.tsx`).
- **Reste du lot** : rôles (administrateur, abonné), limites des offres Gratuit et Premium, paiement (seulement après validation du produit).

---

## Lots 27 à 46 — Plan de lancement

📋 Planifiés le 13 octobre 2026 après l'étude de marché et l'audit
([rapport](etude-marche/rapport-lucidnews-2026-10.html)). Détail, dépendances et critères :
[Plan.md](../Plan.md).

| Phase | Lots | Objet |
|---|---|---|
| A — Finalisation fonctionnelle | 27 Rôles et isolation · 28 Cycle de vie du compte · 29 Newsletter en libre-service | Rendre l'application vendable à plusieurs clients |
| B — Tests et sécurité | 30 Sécurité applicative · 31 Bout en bout et CI · 12 bis Preuve de qualité | Livrer sans régression, prouver la fiabilité |
| C — Préparation de la production | 32 Exécution serveur · 33 E-mail en production · 34 Données · 35 Observabilité et coûts · 36 Conformité | Tourner seul, sans perte, légalement |
| D — Hébergement et déploiement | 37 Hébergement · 38 Bêta privée | Mettre en ligne, mesurer |
| E — Après le lancement | 39 Fil d'un événement · 40 Tendances · 41 Alertes · 42 Offres et paiement · 43 Équipes · 44 Sources personnelles · 45 Arabe · 46 PostgreSQL | Différencier et monétiser |

**Prochain lot : 27 — Rôles et isolation des comptes.** Constat de l'audit : un compte
connecté a aujourd'hui accès à tout, et les routes d'administration dépendent de l'écoute en
local, ce qui ne tient pas derrière un reverse proxy.

## Paramètres : où ils vivent et comment ils s'appliquent

Un paramètre n'est ajouté que s'il est réellement appliqué par le système.

| Paramètre | Portée | Page | Appliqué par | Lot |
|---|---|---|---|---|
| Langues de génération | Toute l'application | Réglages | Enrichissement (une version par langue) | 16 |
| Langue reçue | Un abonné | Préférences | Choix de la version à envoyer | Existant |
| Domaines suivis | Toute l'application | Sources › Domaines | Couverture et filtre du digest | 18 |
| Domaines reçus | Un abonné | Préférences | Sélection par abonné | Existant |
| Sources actives | Toute l'application | Sources | Collecte | 17 |
| Sources reçues | Un abonné | Préférences | Sélection par abonné | Existant |
| Fréquence de génération | Toute l'application | Réglages › Runs | Planification | 20 |
| Fréquence de réception | Un abonné | Préférences | Envoi quotidien ou hebdomadaire | 21 |
| Importance minimale, infos non confirmées, nombre de news | Un abonné | Préférences | Sélection par abonné | Existant |
| Niveau de détail des résumés | Un abonné | Préférences | Rendu de l'e-mail | 21 |
| Critères de pertinence (seuils par profil, étiquettes exclues) | Toute l'application | Réglages | Sélection du digest | 16 |

**Écartés** : consignes IA personnalisées par abonné (coût IA multiplié par le nombre d'abonnés), longueur de résumé générée à la demande (demanderait un appel IA par abonné ; le niveau de détail réutilise les textes déjà produits).

## Blocages et décisions en attente

| Sujet | Bloque | Recommandation |
|---|---|---|
| Clé Resend et service public en HTTPS | La preuve « un vrai e-mail part et ses liens marchent » | Accord demandé : clé Resend, domaine d'envoi vérifié, adresse publique du service. |
| Fuseau horaire du lecteur | Rien | Reporté : demande une tâche d'envoi fréquente. Recommandation : lot 22 bis seulement si des lecteurs sont dans d'autres fuseaux. |
| Envoi SMTP réel | La preuve « l'e-mail arrive tel qu'il est prévisualisé » | Accord demandé : un envoi de test vers une adresse à toi, avec un compte SMTP configuré (aucun aujourd'hui). |
| Vrai run IA lancé depuis l'interface | La preuve « même édition qu'en terminal » | Accord demandé : un run sur une copie des données, avec la clé IA. |
| Vraie tâche launchd | — | Fait : tâche de test chargée sur une copie des données, déclenchée à l'heure prévue, run en succès (IA désactivée, 0 token), puis retirée (aucun agent restant). |
| Annotations du lot 12 | Les chiffres de filtrage du lot 19 (affichés « échantillon insuffisant » d'ici là) | Annoter au fil de l'eau. |
| Domaines personnalisés au-delà des 12 catégories | Tranché : les 12 catégories (lot 18) | — |
| Méthode de planification des runs | Tranché : tâche système launchd générée par l'interface (lot 20) | — |
| Source X (Twitter) | Rien | Lecture seule dans l'interface : elle dépend de cookies ou d'un jeton Apify. |

## Analyse : besoins d'une newsletter moderne

| Besoin | Utilité | Données | Dépendances | Backend | Frontend | Risques | Décision |
|---|---|---|---|---|---|---|---|
| Envoi hebdomadaire | Lecteurs qui ne veulent pas un e-mail par jour | Archive (`items_between`) | Planification | Sélection de la semaine | Aucun (choix existant) | Doublons d'une semaine sur l'autre | Fait, lot 21 |
| Niveau de détail | Lecture rapide ou approfondie | Blocs d'enrichissement existants | Rendu e-mail | Rendu à deux niveaux | Champ de préférence | Aucun coût IA | Fait, lot 21 |
| Aperçu de la newsletter | Vérifier avant d'envoyer | Préférences + digest | Rendu e-mail | Route d'aperçu | Cadre isolé | HTML de source mal échappé | Fait, lot 21 |
| Double opt-in et désinscription signée | Conformité (RGPD), réputation d'envoi | Jetons, statut d'abonné | Fournisseur d'e-mails | Jetons signés, routes publiques | Statut | Clé de signature à protéger | Fait, lot 22 |
| Fournisseur transactionnel | Délivrabilité, rebonds | Clé du fournisseur | Lot 16 | Adaptateur | Aucun | Coût, dépendance externe | Fait (Resend ou SMTP), lot 22 |
| Journal des envois | Savoir ce qui est parti et ce qui a échoué | Table des envois | Lot 22 | Écriture à chaque envoi | Liste | Données personnelles à limiter | Fait, lot 22 |
| Recherche dans l'archive | Retrouver une info passée | Archive | Aucune | Index FTS5 | Recherche | Taille de l'index | Retenu, lot 23 |
| Statistiques d'ouverture et de clic | Mesurer l'intérêt | Pixels et liens suivis | Fournisseur | Webhooks | Graphiques | Vie privée, consentement | Reporté (après le lot 22, sur décision) |
| Alertes immédiates (news critiques) | Ne pas attendre l'édition | Importance « critique » | Planification, envoi fiable | Envoi hors édition | Préférence | Trop d'e-mails | Reporté |
| Flux RSS des éditions | Lire dans un lecteur RSS | Éditions | Aucune | Route RSS | Lien | Faible | Reporté (simple, à ajouter si demandé) |
| Favoris, « à lire plus tard » | Garder une news | Lien news-utilisateur | Comptes | Table | Bouton | Aucun sans comptes | Reporté au lot 26 |

---

# Annexes

## Points observés à confirmer

| Observation | Où | Suite |
|---|---|---|
| 18 sources sur 29 n'ont rien collecté sur les 8 runs archivés. | Lot 8 | À confirmer avec des runs quotidiens. Elles passeront « silencieuses » après 5 runs vides. |
| La corroboration n'a pas encore joué sur un vrai run. | Lot 5 | À observer. Le lot 14 bis augmente les chances (news sous le seuil et 72 h d'archive). |
| La qualité d'un rapprochement « même événement » fait par l'IA. | Lot 14 bis | À surveiller avec l'écran Qualité (« faux fiables ») : un mauvais rapprochement avec un site officiel donnerait « Confirmé ». |
| Un compte officiel est vu comme une source communautaire (cas curl). | Lot 9 | ✅ Réglé au lot 13. |
| 13 domaines de l'archive restent inconnus du registre (blogs personnels, sites de projets, phys.org…). | Lot 13 | À trier au fil des runs, après vérification de chaque site. |
| Aucun compte X officiel n'est inscrit (non vérifiable sans connexion). | Lot 13 | À ajouter dans `reliability.accounts` par la personne qui gère le projet. |
| Les comptes GitHub suivis ne sont pas filtrables dans les préférences (leurs news portent le dépôt). | Lot 10 | À revoir si le besoin apparaît. |
| Quota journalier exact de `gemini-3.5-flash-lite` sur l'offre gratuite. | Lot 5 | À confirmer. Un run de 24 h a consommé environ 140 000 tokens. |
| Choix de l'offre IA pour la production. | Lot 1 | Décision à prendre. |
| Message exact d'un quota épuisé chez chaque fournisseur. | Lot 14 | Gemini : format de l'erreur vérifié dans le code du SDK. Autres fournisseurs : d'après leur documentation. À confirmer lors d'un vrai épuisement. |
| Une édition passée montre l'état le plus récent de ses news : une news publiée « Sans analyse IA » y apparaît avec son analyse après le run qui l'a analysée, même si son score est bas. | Lot 14 | Comportement de l'archive (une ligne par news). À figer par édition si cela gêne. |

## Décisions prises

| Question | Décision |
|---|---|
| Nom du produit | LucidNews |
| Fonctions retirées | WeChat, README zh/ja, site Pages, Finance + OpenBB |
| Profil `ai-creator` | Gardé, traduit en anglais |
| Plan de la phase 2 | Archive → échecs IA → santé des sources → corroboration → évaluation → registre |
| Sources mortes | Retirées de la config locale |
| Premier écran | Édition du jour, avec de vraies données |
| API | En Python, à côté du moteur |
| Images des modèles | Non versionnées (`Templates/` ignoré) |
| Lot après Archives et Sources | Fiche d'une news |
| Préférences | Version locale, sans comptes (A) |
| Lot après Préférences | Mesure de la qualité (A) |
| Registre de confiance | Lancé avant la fin des annotations ; seulement des comptes et sites vérifiés à la main |
| Lot après le registre | Budget IA et réutilisation de l'enrichissement d'abord (A) |
| Quota IA épuisé | L'application continue et affiche les news sans analyse IA, seulement dans ce cas |
| Lot après le lot 14 | Lot 14 bis (recommandation A, prise par défaut) |
| Interface complète (9 oct.) | Plan revu : lots 15 à 26 réordonnés, une seule page ajoutée (Réglages) |
| Clés API depuis l'interface | Fichier `.env` du projet, droits 600, jamais réaffichées |
| Domaines surveillés | Les 12 catégories existantes (A) |
| Planification des runs | Tâche système launchd générée par l'interface (B) |
| X (Twitter) dans l'interface | Lecture seule (cookies ou jeton Apify impossibles à vérifier depuis l'écran) |
| Compteurs de doublons des anciens runs | Pas reconstitués : ils commencent au premier run après le lot 19 |
| Seuil de lacune d'un domaine | Moins de 2 sources actives ou moins de 3 news sur la période, réglable dans l'onglet Domaines |
| Rôle du score de qualité | Départager les news de même score, sans jamais passer devant une news mieux notée |
| Style des réponses | Skill explainer : français simple, sections, questions oui/non |

## Historique des commits

| Commit | Date | Lot | Message |
|---|---|---|---|
| `57432f9` | 2026-10-06 | 1 | import Horizon baseline (MIT, © 2026 Thysrael) |
| `e9cd02b` | 2026-10-06 | 1 | rebrand to LucidNews and drop legacy Horizon-specific features |
| `70c1f41` | 2026-10-06 | 1 | harden digest selection, rendering and source config |
| `22da2c9` | 2026-10-06 | 1 | reliability scoring, IT category taxonomy and en/fr localization |
| `e9d1b64` | 2026-10-06 | 1 | subscriber preferences, plan hooks and per-preference delivery |
| `8a745a8` | 2026-10-06 | 1 | curated IT source catalog and documented environment |
| `2cc5721` | 2026-10-06 | 1 | AI request quota limiter, classifier retries and product documentation |
| `0b6f852` | 2026-10-06 | 1 | ignore local config copies, env variants and key files |
| `d62ca35` | 2026-10-06 | 1 | readable apostrophes in digests and localized content-angle prefix |
| `c01db56` | 2026-10-06 | 1 | fix leftover command name in configuration guide |
| `933b55a` | 2026-10-06 | 2 | SQLite archive of runs and items with analysis reuse |
| `47b4110` | 2026-10-06 | 3 | retry items whose AI analysis or enrichment failed |
| `f2269ab` | 2026-10-06 | 4 | per-source health tracking and lucidnews-sources report |
| `54f0e88` | 2026-10-06 | 5 | corroboration by independent publishers |
| `9e0496c` | 2026-10-07 | 6, 7, 8 | read-only API and React app (edition, archive, source health) |
| `2e77a82` | 2026-10-08 | 9 | item detail page with full reliability breakdown |
| `efc5fbb` | 2026-10-08 | 10 | local subscriber preferences screen |
| `337b0a2` | 2026-10-08 | 11 | hand-annotation quality evaluation |
| `b7abe50` | 2026-10-09 | — | lots overview (closed and upcoming work) |
| `b1c18cf` | 2026-10-09 | 13 | social accounts as publishers and wider trust registry |
| `7bcd919` | 2026-10-09 | 14 | run token budget, non-blocking quota exhaustion and enrichment reuse |
| `0429fc7` | 2026-10-09 | 14 bis | wider corroboration, source quality and archive reassessment |
| `3368611` | 2026-10-09 | 15 | interactive news cards and revised product plan |
| `1bdaf2b` | 2026-10-10 | 16, 17 | settings, API keys and sources managed from the web app |
| `1850d32` | 2026-10-10 | 18 | watched domains, coverage from the archive and recommended sources |
| `8c8802f` | 2026-10-11 | 19, 20 | quality overview, start and schedule runs from the web app |
