# Nouveaux secteurs — finance, juridique, santé, énergie

> Ouvrir LucidNews à quatre métiers en plus de la tech. Chaque installation suit un secteur,
> choisi dans Réglages, avec ses domaines, sa consigne pour l'IA, ses sources fiables et ses
> autorités. Pour les administrateurs qui vendent ou utilisent une veille métier.

| | |
|---|---|
| **Date et version** | 21 novembre 2026, v1 |
| **Auteur** | Claude, pour Oussama |
| **Branche de travail** | `dev` (dépôt perso `oussamaalmouallim/LucidNews`) ; `main` seulement sur validation |
| **État** | 22/11/2026 — Phase 1 **clôturée**. Phases 2 (Finance), 3 (Juridique) et 4 (Santé) : lots x.1 à x.4 faits (collecte seule, décision 11) ; relectures 2.5, 3.5 et 4.5 en attente d'une IA avec quota. Prochaine : phase 5 (Énergie et climat). |

---

## Sommaire

- [Le problème et le but](#probleme)
- [Décisions prises](#decisions)
- [Ce qu'on a trouvé](#constats)
- [Comment les morceaux s'emboîtent](#emboitement)
- [Phases non clôturées](#phases-ouvertes)
  - [Phase 2 — Secteur Finance](#phase-2) : [2.1](#lot-2-1) · [2.2](#lot-2-2) · [2.3](#lot-2-3) · [2.4](#lot-2-4) · [2.5](#lot-2-5)
  - [Phase 3 — Secteur Juridique et réglementaire](#phase-3) : [3.1](#lot-3-1) · [3.2](#lot-3-2) · [3.3](#lot-3-3) · [3.4](#lot-3-4) · [3.5](#lot-3-5)
  - [Phase 4 — Secteur Santé et pharma](#phase-4) : [4.1](#lot-4-1) · [4.2](#lot-4-2) · [4.3](#lot-4-3) · [4.4](#lot-4-4) · [4.5](#lot-4-5)
  - [Phase 5 — Secteur Énergie et climat](#phase-5) : [5.1](#lot-5-1) · [5.2](#lot-5-2) · [5.3](#lot-5-3) · [5.4](#lot-5-4) · [5.5](#lot-5-5)
  - [Phase 6 — Fin du chantier](#phase-6) : [6.1](#lot-6-1) · [6.2](#lot-6-2) · [6.3](#lot-6-3)
- [Phases clôturées](#phases-cloturees)
  - [Phase 1 — Mécanique commune des secteurs](#phase-1) : [1.1](#lot-1-1) · [1.2](#lot-1-2) · [1.3](#lot-1-3) · [1.4](#lot-1-4) · [1.5](#lot-1-5) · [1.6](#lot-1-6) · [1.7](#lot-1-7)
  - [Phase 0 — Socle multi-secteurs (lot 47)](#phase-0)
- [Actions de l'utilisateur](#actions)
- [Points à confirmer](#a-confirmer)
- [Décidé automatiquement](#auto)
- [Zone technique concernée](#zone-technique)

---

<a id="probleme"></a>
## Le problème et le but

**Aujourd'hui.** LucidNews ne sait suivre que la tech. Le socle est posé : le secteur se choisit
dans Réglages, les catégories viennent du serveur, l'IA ne reçoit que celles du secteur. Mais
seule la tech est installée. Ses sources, sa consigne pour l'IA et son registre de confiance
(la liste des éditeurs jugés fiables) ne parlent que de tech. La page de connexion dit « La
veille tech ».

**Le but.** Quatre secteurs prêts à l'emploi. L'administrateur choisit un secteur dans Réglages.
L'application lui prépare tout : domaines, consigne pour l'IA, sources fiables déjà vérifiées et
autorités reconnues comme sources officielles. Le premier run produit une édition rangée par les
domaines du secteur.

| Besoin | Où ce sera |
|---|---|
| Choisir le secteur | Réglages, carte « Ce que couvre la veille » (existe) |
| Les domaines d'un secteur | Édition, filtres, Ma veille, recherche, Sources (lot 47) |
| Des sources fiables, prêtes | Le catalogue du secteur, appliqué au changement de secteur |
| Les autorités comptent comme officielles | Le registre de confiance, complété par secteur |
| Une IA qui comprend le métier | Un profil éditorial (consigne) par secteur |
| Des sources sans flux RSS | Un lecteur de pages de liste, limité aux sites officiels |

---

<a id="decisions"></a>
## Décisions prises

| # | Date | Sujet | Choix | Conséquence dans le plan |
|---|---|---|---|---|
| 1 | 30/10/2026 | Quels secteurs | Finance, juridique et réglementaire, santé et pharma, énergie et climat | Phases 2 à 5 |
| 2 | 30/10/2026 | Combien par installation | Un seul, choisi par l'administrateur dans Réglages | Phase 0 ; lot 1.4 |
| 3 | 30/10/2026 | Changer de secteur | Remplace les sources : les anciennes sont désactivées, pas supprimées | Lot 1.4 |
| 4 | 30/10/2026 | Les sources | LucidNews les cherche et les prépare lui-même ; elles doivent être fiables | Lots 1.5, 2.3, 3.3, 4.3, 5.3 |
| 5 | 30/10/2026 | Méthode git | Travail sur `dev` ; `main` seulement quand l'utilisateur valide | Lot 6.3 |
| 6 | 22/11/2026 | Ordre des secteurs (D1) | Finance, juridique, santé, énergie | Phases 2 à 5 dans cet ordre |
| 7 | 22/11/2026 | Sources sans RSS (D2) | A : lecteur de pages de liste, limité aux sites officiels, respect de `robots.txt`, lecture lente | Lot 1.6 ; les lots 2.3, 3.3, 4.3 et 5.3 peuvent s'en servir |
| 8 | 22/11/2026 | Langues des sources (D3) | Français et anglais ; l'édition reste traduite | Lots 2.3, 3.3, 4.3, 5.3 |
| 9 | 22/11/2026 | Runs réels avec l'IA (D4) | Oui, avec un budget de tokens par run | Lots 2.4, 3.4, 4.4, 5.4 |
| 10 | 22/11/2026 | Commit `e56476e` au message faux (D5) | On le laisse ; le journal des lots l'explique | Journal des lots, lot 47 |
| 11 | 22/11/2026 | Runs réels avec l'IA (révise la décision 9) | Arrêtés : l'offre d'IA gratuite ne tient pas un run. On valide la **collecte** seule, source par source, sans IA | Lots 2.4, 3.4, 4.4, 5.4 ; lot 2.5 en attente d'une IA avec quota |
| 12 | 22/11/2026 | GDELT et Google News dans les secteurs | Prêts mais **désactivés d'office** : ils font entrer des sites et des conseils qu'on ne contrôle pas | Lots 2.3, 3.3, 4.3, 5.3 |
| 13 | 22/11/2026 | Phase 2 non clôturée | On passe à la phase 3 ; la relecture 2.5 attend une IA avec quota | Phases 2 à 5 : lots x.5 en attente |

---

<a id="constats"></a>
## Ce qu'on a trouvé

**Le socle (vérifié le 21/11/2026)**

- Le lot 47 est sur `dev` et poussé (`origin/dev` = `e56476e`). Son message de commit est faux : il parle d'épargne (« feat(savings)… »), un texte venu d'un autre projet. Le contenu est bien le lot 47 (`git show --stat e56476e`).
- Le secteur `tech` est le seul du registre des secteurs. Les identifiants de catégorie sont vérifiés uniques entre secteurs au démarrage.
- La page de connexion affiche « La veille tech à laquelle on peut se fier. » (texte `auth.brand.title`).

**Les sources (vérifié le 21/11/2026)**

- Le catalogue est la configuration d'exemple : 31 flux RSS tech, 4 dépôts GitHub. Un flux RSS porte déjà `category`, `profile` et `trust` (rang de confiance imposé à l'éditeur).
- Deux sources par mot-clé existent, désactivées, avec des requêtes tech : GDELT (base mondiale d'articles de presse) et Google News. Elles peuvent servir un secteur avec ses propres requêtes.
- Le catalogue de l'assistant d'installation ne connaît que des domaines tech.
- Il n'existe aucun lecteur de pages web sans flux RSS.

**L'IA et la fiabilité (vérifié le 21/11/2026)**

- Trois profils éditoriaux, tous tech. Le profil par défaut, `tech-news`, écarte même la « couverture d'abord financière ».
- Le registre de confiance des éditeurs est une liste écrite dans le code, uniquement tech. La configuration peut le compléter (`reliability.domains`).
- L'IA est activée dans la configuration locale. Les catégories d'une news viennent de l'IA. Sans IA, une news est rangée par le domaine habituel de sa source.

**À confirmer** : quelles autorités publient un flux RSS public et stable (AMF, ACPR, Légifrance, CNIL, HAS, ANSM, CRE, ADEME…). C'est vérifié flux par flux aux lots 2.3, 3.3, 4.3 et 5.3.

---

<a id="emboitement"></a>
## Comment les morceaux s'emboîtent

```text
Réglages ──► PUT /api/settings/sector ──► config.json : sector, sources, profil
                                              │
          catalogue du secteur ───────────────┤  (sources vérifiées, requêtes, autorités)
                                              ▼
run du pipeline ──► collecte ──► IA (consigne du secteur, catégories du secteur)
                                              │
              registre de confiance + autorités du secteur ──► étiquettes de fiabilité
                                              ▼
                               Édition rangée par domaine du secteur
```

- Un secteur = un paquet : catégories, profil, catalogue, autorités. Tout passe par le registre des secteurs.
- Le catalogue ne contient que des sources **vérifiées par l'outil du lot 1.5**.
- Changer de secteur ne supprime rien : les sources d'un autre secteur sont désactivées, et l'archive reste lisible.
- La tech ne change pas : chaque phase se clôt avec toute la suite de tests existante au vert.

---

<a id="phases-ouvertes"></a>
## Phases non clôturées

<a id="phase-2"></a>
## Phase 2 — Secteur Finance

**Objectif** : une installation en secteur Finance produit une édition finance fiable.
**Résultat de phase** : choisir « Finance » dans Réglages, lancer un run, et lire une édition rangée par domaines finance, avec des étiquettes de fiabilité justes.

<a id="lot-2-1"></a>
### Lot 2.1 — Les domaines de la finance

- **Objectif** : 8 domaines, avec leurs noms en français et en anglais, leur portée pour l'IA et leurs icônes.
- **À faire** : marchés, banques, assurance, crypto-actifs, fusions-acquisitions, macroéconomie, régulation financière, fintech ; identifiants uniques (`finance-…`), alias, icônes.
- **Dépend de** : phase 1.
- **Tests du lot** : identifiants uniques, libellés FR/EN présents, portée lue dans la consigne.
- **Résultat attendu** : « Finance » apparaît dans Réglages avec ses 8 domaines.
- **Fait (2026-11-22)** : secteur `finance` dans le registre, 8 domaines (`finance-markets`, `-banking`, `-insurance`, `-crypto`, `-deals`, `-macro`, `-regulation`, `-fintech`), libellés FR/EN, portée pour l'IA, alias, icônes ; règle « jamais de conseil ». Les mots tech (« LLM », « security ») restent à la tech. Le secteur factice des tests a reçu des mots à lui (« Banque » est désormais un mot de la finance). Preuve : `tests/test_finance_sector.py` (lot 2.1, 4 tests).

<a id="lot-2-2"></a>
### Lot 2.2 — La consigne finance

- **Objectif** : l'IA note une news finance comme un analyste prudent.
- **À faire** : profil `finance-news` (routage, grille de score, rédaction) ; jamais de conseil d'investissement ; un chiffre ou une prévision ne vaut que si la source le donne.
- **Dépend de** : 2.1.
- **Tests du lot** : consigne construite avec le profil finance ; règle « pas de conseil » présente.
- **Résultat attendu** : la consigne finance est lisible dans les tests.
- **Fait (2026-11-22)** : profil `profiles/finance-news/` : routage (écarte conseils, prédictions de cours, contenus sponsorisés), grille de score d'analyste prudent (banque centrale et régulateurs en tête, une prévision n'est jamais un fait), rédaction en trois blocs (résumé, contexte, conséquence) sans recommandation d'achat ou de vente. Preuve : `tests/test_finance_sector.py` (lot 2.2, 3 tests) ; l'ordre des profils de l'édition inclut le nouveau profil (`tests/test_balanced_digest.py`).

<a id="lot-2-3"></a>
### Lot 2.3 — Les sources finance

- **Objectif** : 15 à 25 sources finance, toutes vérifiées par l'outil 1.5.
- **À faire**
  - Chercher les flux des autorités (AMF, ACPR, Banque de France, BCE, ESMA, SEC) et des éditeurs reconnus qui offrent un flux gratuit. Écarter les contenus payants.
  - Requêtes GDELT et Google News finance, en français et en anglais (décision 8).
  - Les autorités entrent dans le catalogue comme sources officielles.
- **Dépend de** : 2.1, 1.5, 1.6.
- **Tests du lot** : le catalogue finance se charge ; le rapport de vérification ne garde aucune source écartée.
- **Résultat attendu** : rapport de vérification daté, avec 15 sources gardées ou plus.
- **Fait (2026-11-22)** : `data/sectors/finance.json` : 24 flux et 1 page officielle, **25 gardées sur 25** (rapport : `docs/sources/verification/finance-2026-11-22.md`). Autorités : BCE (deux flux), Fed, Banque d'Angleterre, INSEE, AMF, EBA, BRI, FSB, SEC, CFTC, ESMA (page lue par le lecteur du lot 1.6) ; presse gratuite : Le Monde, Le Figaro, BFM Business, CNBC, MarketWatch, CoinDesk, The Block, Decrypt, Finextra, Maddyness, Crunchbase News, Insurance Journal, Reinsurance News. Les 8 domaines ont chacun une source. 16 autorités en `official`, 13 éditeurs en `reputable`. GDELT (mots FR et EN, sans filtre de langue) et Google News (EN) activés. **Écartées** : Banque de France, ACPR, Les Echos, Argus de l'assurance, OCDE, OFAC (accès refusé, 403), FMI, EIOPA (404), FCA (news sans date), Financial Times (payant). **En plus du prévu** : le vérificateur ignore une date dans le futur (Finextra annonçait un événement de 2027) ; le lecteur de pages accepte `title_selector`, quand le lien couvre aussi la date et le chapeau (ESMA). Preuve : `tests/test_finance_sector.py` (lot 2.3, 3 tests), `tests/test_source_check.py`, `tests/test_page_sources.py`.

<a id="lot-2-4"></a>
### Lot 2.4 — Run réel en finance

- **Objectif** : un vrai run, sur une copie des données, produit une édition finance.
- **À faire** : copie des données dans le dossier temporaire ; bascule en Finance ; run avec l'IA et un budget de tokens (décision 9) ; contrôle des domaines, des étiquettes et des sources ; copie supprimée ensuite.
- **Dépend de** : 2.2, 2.3.
- **Tests du lot** : le run se termine en succès ; aucune news rangée « Autre » par erreur de domaine.
- **Résultat attendu** : capture de l'édition finance, et nombre de news par domaine noté dans le plan.
- **Fait (2026-11-22), en collecte seule (décision 11)** : sur une copie des données Docker, basculée en Finance comme le fait Réglages (27 sources ajoutées, 33 sources tech désactivées), collecte sur 7 jours sans IA. **Les 27 sources ramènent des news**, 338 au total : crypto-actifs 82, économie 64, marchés 62, assurance 40, fintech 32, régulation 25, fusions 20, banques 5 + 12 avec les deux sources ajoutées. Contrôle : aucune news sans titre, aucun lien hors HTTPS, aucun doublon, rien hors de la fenêtre. Le run avec l'IA (Gemini gratuit, 10 requêtes par minute) a été arrêté à l'analyse, sur ta demande. **Corrigé en chemin** : la collecte écarte une news datée de plus d'un jour dans le futur (8 annonces d'événements Finextra, jusqu'en février 2027, auraient trôné en tête de l'édition) ; GDELT (75 news de sites inconnus en toutes langues) et Google News (conseils de bourse, puis refus 429) sont **désactivés** dans le catalogue finance, leurs requêtes gardées ; les banques, trop peu couvertes, reçoivent l'OCC (superviseur américain) et Banking Dive. Copies supprimées. Preuve : `tests/test_future_items.py`, `tests/test_finance_sector.py`.

<a id="lot-2-5"></a>
### Lot 2.5 — Ta relecture de l'édition finance

- **Objectif** : un regard métier sur la qualité, avant de passer au secteur suivant.
- **À faire** : **Toi** : lire l'édition du lot 2.4 et noter ce qui manque ou ce qui est faux ; Claude corrige les sources ou la consigne.
- **Dépend de** : 2.4.
- **Tests du lot** : les corrections ont leurs tests.
- **Résultat attendu** : ton accord écrit sur l'édition finance.

**Clôture de la phase 2** : toute la suite (Python, interface, parcours), build, et un second run réel en finance après les corrections du lot 2.5.

---

<a id="phase-3"></a>
## Phase 3 — Secteur Juridique et réglementaire

**Objectif** : une veille juridique fiable : textes, décisions, autorités.
**Résultat de phase** : en secteur Juridique, l'édition range législation, jurisprudence, données personnelles… avec les textes officiels marqués comme tels.

<a id="lot-3-1"></a>
### Lot 3.1 — Les domaines du juridique

- **Objectif** : 7 à 8 domaines, avec leurs noms FR/EN, leur portée pour l'IA et leurs icônes.
- **À faire** : législation, jurisprudence, droit des affaires, droit du travail, données personnelles, droit européen, conformité, droit public ; identifiants `legal-…`.
- **Dépend de** : phase 2 clôturée.
- **Tests du lot** : identifiants uniques, libellés, portée.
- **Résultat attendu** : « Juridique et réglementaire » dans Réglages avec ses domaines.
- **Fait (2026-11-22)** : secteur `legal`, 8 domaines (`legal-legislation`, `-case-law`, `-business`, `-employment`, `-data-protection`, `-eu`, `-compliance`, `-public`), libellés FR/EN, portée, alias, icônes ; règle « jamais de conseil ». Les mots déjà pris gardent leur secteur (« compliance » reste à la finance). Preuve : `tests/test_legal_sector.py` (lot 3.1, 3 tests).

<a id="lot-3-2"></a>
### Lot 3.2 — La consigne juridique

- **Objectif** : l'IA distingue un texte adopté, un projet de texte et un commentaire.
- **À faire** : profil `legal-news` ; une décision ou un texte publié par l'institution compte comme confirmé ; jamais de conseil juridique ; date d'entrée en vigueur citée seulement si la source la donne.
- **Dépend de** : 3.1.
- **Tests du lot** : consigne construite, règles présentes.
- **Résultat attendu** : la consigne juridique est lisible dans les tests.
- **Fait (2026-11-22)** : profil `profiles/legal-news/` : l'IA identifie le stade du texte (proposition, projet, adopté, publié, en vigueur, arrêt, conclusions) ; un texte publié par l'institution est la source première ; date d'entrée en vigueur seulement si la source la donne ; jamais un projet présenté comme loi. Preuve : `tests/test_legal_sector.py` (lot 3.2, 3 tests).

<a id="lot-3-3"></a>
### Lot 3.3 — Les sources juridiques

- **Objectif** : 15 à 25 sources juridiques vérifiées.
- **À faire** : Légifrance et le Journal officiel, EUR-Lex, Conseil d'État, Cour de cassation, Conseil constitutionnel, CNIL, et des éditeurs juridiques à flux gratuit ; écarter le payant ; passage par l'outil 1.5.
- **Dépend de** : 3.1, 1.5, 1.6.
- **Tests du lot** : catalogue chargé ; rapport sans source écartée.
- **Résultat attendu** : rapport de vérification daté, avec 15 sources gardées ou plus.
- **Fait (2026-11-22)** : `data/sectors/legal.json` : 16 flux et 4 pages officielles, **20 gardées sur 20** (rapport : `docs/sources/verification/legal-2026-11-22.md`). Institutions : Service-public.fr (professionnels), Sénat (textes), Conseil d'État, CNIL, DGCCRF, ANACT, DOJ ; pages lues par le lecteur du lot 1.6 : Conseil constitutionnel, Cour de justice de l'UE, Autorité de la concurrence, EDPB. Presse : Dalloz actualité, Le Monde Justice, SCOTUSblog, Village de la Justice, Personnel Today, HR Dive, noyb, Euractiv France, Compliance Week. **Écartées** : Légifrance (son robots.txt interdit la lecture), Cour de cassation (page construite par script, sans flux), EUR-Lex, Parlement européen, EDPS, ICO, FTC, Actu-Juridique (403 ou 404), Autorité de la concurrence en flux (59 jours sans news, lue par sa page), Legalis, Le Petit Juriste (trop anciens). GDELT et Google News prêts mais désactivés (décision 12). **En plus du prévu** : le lecteur de pages suit la balise `<base>` d'une page (liens CJUE en 404 sinon) ; le vérificateur lit les dates mal formées que le collecteur lit déjà (Sénat). Preuve : `tests/test_legal_sector.py` (lot 3.3, 3 tests), `tests/test_page_sources.py`, `tests/test_source_check.py`.

<a id="lot-3-4"></a>
### Lot 3.4 — Run réel en juridique

- **Objectif** : un vrai run produit une édition juridique.
- **À faire** : même déroulé que le lot 2.4, en secteur Juridique.
- **Dépend de** : 3.2, 3.3.
- **Tests du lot** : run en succès ; les textes officiels ont le rang officiel.
- **Résultat attendu** : capture de l'édition et chiffres par domaine notés dans le plan.
- **Fait (2026-11-22), en collecte seule (décision 11)** : copie des données Docker basculée en Juridique (20 sources ajoutées, 33 tech désactivées), collecte sur 7 jours sans IA : **207 news**, 18 sources sur 20 en ramènent (ANACT et noyb n'ont rien publié depuis 9 et 24 jours). Par domaine : droit européen 56, conformité 54, jurisprudence 43, travail 25, données personnelles 14, législation 10, affaires 4, droit public 1. Aucune news sans titre, hors HTTPS, en double ou hors fenêtre. **Corrigé en chemin** : le lecteur de pages suit les redirections (CJUE 302, EDPB 301 : 0 news avant, 14 après) ; un lien http vers le site même d'un flux HTTPS passe en https (Sénat, Conseil d'État). Les institutions ont le rang officiel (test). Copie supprimée. **Faible** : droit public et droit des affaires, peu de sources libres trouvées. Preuve : `tests/test_page_sources.py`, `tests/test_rss_secure_links.py`, `tests/test_legal_sector.py`.

<a id="lot-3-5"></a>
### Lot 3.5 — Ta relecture de l'édition juridique

- **Objectif** : un regard métier avant le secteur suivant.
- **À faire** : **Toi** : relire l'édition ; Claude corrige.
- **Dépend de** : 3.4.
- **Tests du lot** : les corrections ont leurs tests.
- **Résultat attendu** : ton accord écrit.

**Clôture de la phase 3** : toute la suite, build, parcours, et second run réel en juridique.

---

<a id="phase-4"></a>
## Phase 4 — Secteur Santé et pharma

**Objectif** : une veille santé prudente, qui ne présente jamais une promesse comme un fait.
**Résultat de phase** : en secteur Santé, l'édition range réglementation, médicaments, essais cliniques… avec des étiquettes plus sévères sur les annonces non confirmées.

<a id="lot-4-1"></a>
### Lot 4.1 — Les domaines de la santé

- **Objectif** : 7 à 8 domaines avec noms FR/EN, portée et icônes.
- **À faire** : réglementation, médicaments, essais cliniques, dispositifs médicaux, santé publique, e-santé, biotechnologies, établissements de santé ; identifiants `health-…`.
- **Dépend de** : phase 3 clôturée.
- **Tests du lot** : identifiants uniques, libellés, portée.
- **Résultat attendu** : « Santé et pharma » dans Réglages avec ses domaines.
- **Fait (2026-11-22)** : secteur `health`, 8 domaines (`health-regulation`, `-drugs`, `-trials`, `-devices`, `-public`, `-digital`, `-biotech`, `-care`), libellés FR/EN, portée, alias, icônes ; règle « jamais de conseil ». Preuve : `tests/test_health_sector.py` (lot 4.1, 3 tests).

<a id="lot-4-2"></a>
### Lot 4.2 — La consigne santé

- **Objectif** : l'IA traite un résultat d'essai ou une annonce de laboratoire avec prudence.
- **À faire** : profil `health-news` ; jamais de conseil médical ; un résultat non publié ou non évalué reste « non vérifié » ; une autorisation de mise sur le marché compte comme confirmée seulement si l'autorité la publie.
- **Dépend de** : 4.1.
- **Tests du lot** : consigne construite, règles présentes.
- **Résultat attendu** : la consigne santé est lisible dans les tests.
- **Fait (2026-11-22)** : profil `profiles/health-news/` : l'annonce d'une entreprise, un communiqué ou une prépublication ne sont pas une preuve (« non vérifié » sans revue à comité de lecture ni avis d'autorité) ; une autorisation n'est confirmée que publiée par l'autorité qui l'accorde ; phase, population et effectif cités quand la source les donne ; jamais de conseil médical ni de « guérison ». Preuve : `tests/test_health_sector.py` (lot 4.2, 3 tests).

<a id="lot-4-3"></a>
### Lot 4.3 — Les sources santé

- **Objectif** : 15 à 25 sources santé vérifiées.
- **À faire** : HAS, ANSM, ministère de la Santé, Santé publique France, EMA, OMS, FDA, et des revues ou éditeurs à flux gratuit ; passage par l'outil 1.5.
- **Dépend de** : 4.1, 1.5, 1.6.
- **Tests du lot** : catalogue chargé ; rapport sans source écartée.
- **Résultat attendu** : rapport de vérification daté, avec 15 sources gardées ou plus.
- **Fait (2026-11-22)** : `data/sectors/health.json` : 20 flux et 2 pages officielles, **22 gardées sur 22** (rapport : `docs/sources/verification/health-2026-11-22.md`). Autorités : HAS, EMA, FDA (communiqués, alertes MedWatch), MHRA, ministère britannique de la Santé, ECDC, CDC, Inserm ; pages : ANSM, Santé publique France. Revues : NEJM, The Lancet, The BMJ, Nature Medicine. Presse : STAT, BioPharma Dive, MedTech Dive, Healthcare Dive, Le Monde Santé, DSIH, Hospitalia. **Écartées** : OMS (flux arrêté depuis 43 jours, page sans news), ministère de la Santé et ANS (pas de flux), NIH, Fierce, Endpoints, MobiHealthNews, MassDevice (403), Egora, What's up doc, ARS (trop anciens) ; payantes ou inconnues : Medscape, Le Quotidien du médecin, Le Quotidien du pharmacien ; les rappels FDA (mêlent l'alimentaire). **En plus du prévu** : le lecteur de pages lit une date ISO année-mois-jour (le 5 novembre était lu 11 mai) et prend la première de deux dates (« publié le … mis à jour le … »). Preuve : `tests/test_health_sector.py` (lot 4.3), `tests/test_page_sources.py`.

<a id="lot-4-4"></a>
### Lot 4.4 — Run réel en santé

- **Objectif** : un vrai run produit une édition santé.
- **À faire** : même déroulé que le lot 2.4, en secteur Santé.
- **Dépend de** : 4.2, 4.3.
- **Tests du lot** : run en succès ; aucune annonce de laboratoire seule n'est « Confirmé ».
- **Résultat attendu** : capture de l'édition et chiffres par domaine notés dans le plan.
- **Fait (2026-11-22), en collecte seule (décision 11)** : copie des données Docker basculée en Santé (22 sources ajoutées, 33 tech désactivées), collecte sur 7 jours sans IA : **193 news**, 21 sources sur 22 en ramènent (HAS : rien depuis le 12/11). Par domaine : essais 55, réglementation 37, biotech 30, santé publique 27, établissements 15, médicaments 11, dispositifs 10, e-santé 8. Aucune news sans titre, hors HTTPS, en double, datée dans le futur ou hors fenêtre. Une annonce de laboratoire seule n'est jamais « Confirmé » : le site d'un laboratoire est inconnu du registre, seule une autorité donne le rang officiel (test). Copie supprimée. Preuve : `tests/test_health_sector.py` (lot 4.4).

<a id="lot-4-5"></a>
### Lot 4.5 — Ta relecture de l'édition santé

- **Objectif** : un regard métier avant le secteur suivant.
- **À faire** : **Toi** : relire l'édition ; Claude corrige.
- **Dépend de** : 4.4.
- **Tests du lot** : les corrections ont leurs tests.
- **Résultat attendu** : ton accord écrit.

**Clôture de la phase 4** : toute la suite, build, parcours, et second run réel en santé.

---

<a id="phase-5"></a>
## Phase 5 — Secteur Énergie et climat

**Objectif** : une veille énergie utile aux acteurs des CEE (certificats d'économies d'énergie), de la rénovation et de l'énergie.
**Résultat de phase** : en secteur Énergie, l'édition range marchés, renouvelables, efficacité et CEE, réglementation, climat.

<a id="lot-5-1"></a>
### Lot 5.1 — Les domaines de l'énergie

- **Objectif** : 7 à 8 domaines avec noms FR/EN, portée et icônes.
- **À faire** : marchés de l'énergie, renouvelables, efficacité énergétique et CEE, rénovation, réseaux et stockage, réglementation, climat et RSE, mobilité ; identifiants `energy-…`.
- **Dépend de** : phase 4 clôturée.
- **Tests du lot** : identifiants uniques, libellés, portée.
- **Résultat attendu** : « Énergie et climat » dans Réglages avec ses domaines.

<a id="lot-5-2"></a>
### Lot 5.2 — La consigne énergie

- **Objectif** : l'IA repère ce qui change pour un professionnel : arrêté, fiche d'opération, prix, échéance.
- **À faire** : profil `energy-news` ; un arrêté ou une délibération publiés comptent comme confirmés ; une échéance citée seulement si la source la donne.
- **Dépend de** : 5.1.
- **Tests du lot** : consigne construite, règles présentes.
- **Résultat attendu** : la consigne énergie est lisible dans les tests.

<a id="lot-5-3"></a>
### Lot 5.3 — Les sources énergie

- **Objectif** : 15 à 25 sources énergie vérifiées.
- **À faire** : CRE, ADEME, ministère de la Transition écologique, RTE, AIE (Agence internationale de l'énergie), Commission européenne (énergie), et des éditeurs spécialisés à flux gratuit ; passage par l'outil 1.5.
- **Dépend de** : 5.1, 1.5, 1.6.
- **Tests du lot** : catalogue chargé ; rapport sans source écartée.
- **Résultat attendu** : rapport de vérification daté, avec 15 sources gardées ou plus.

<a id="lot-5-4"></a>
### Lot 5.4 — Run réel en énergie

- **Objectif** : un vrai run produit une édition énergie.
- **À faire** : même déroulé que le lot 2.4, en secteur Énergie.
- **Dépend de** : 5.2, 5.3.
- **Tests du lot** : run en succès ; les arrêtés et délibérations ont le rang officiel.
- **Résultat attendu** : capture de l'édition et chiffres par domaine notés dans le plan.

<a id="lot-5-5"></a>
### Lot 5.5 — Ta relecture de l'édition énergie

- **Objectif** : un regard métier, le tien en premier pour les CEE.
- **À faire** : **Toi** : relire l'édition ; Claude corrige.
- **Dépend de** : 5.4.
- **Tests du lot** : les corrections ont leurs tests.
- **Résultat attendu** : ton accord écrit.

**Clôture de la phase 5** : toute la suite, build, parcours, et second run réel en énergie.

---

<a id="phase-6"></a>
## Phase 6 — Fin du chantier

**Objectif** : livrer les cinq secteurs sur `main`, documentés.
**Résultat de phase** : `main` contient les secteurs, la CI est verte, la documentation dit comment choisir et ajouter un secteur.

<a id="lot-6-1"></a>
### Lot 6.1 — Bascule complète des cinq secteurs

- **Objectif** : vérifier que les cinq secteurs basculent l'un vers l'autre sans perte.
- **À faire** : un parcours Playwright passe par chaque secteur dans Réglages et revient à la tech ; les sources reviennent à l'identique.
- **Dépend de** : phases 1 à 5.
- **Tests du lot** : ce parcours, plus toute la suite.
- **Résultat attendu** : parcours vert, sur l'application compilée.

<a id="lot-6-2"></a>
### Lot 6.2 — Documentation

- **Objectif** : un administrateur sait choisir un secteur ; un développeur sait en ajouter un.
- **À faire** : README (secteur de la veille), journal des lots, architecture, guide « ajouter un secteur » (catalogue, profil, autorités, vérification).
- **Dépend de** : 6.1.
- **Tests du lot** : les liens de la documentation mènent à des fichiers qui existent.
- **Résultat attendu** : le guide permet d'ajouter un sixième secteur sans lire le code.

<a id="lot-6-3"></a>
### Lot 6.3 — Validation et passage sur `main`

- **Objectif** : la version validée arrive sur `main`.
- **À faire** : **Toi** : dire que la version est validée. Claude prépare la fusion de `dev` vers `main` ; tu pousses.
- **Dépend de** : 6.2.
- **Tests du lot** : la CI de `main` est verte.
- **Résultat attendu** : `main` contient les cinq secteurs, CI verte sur GitHub.

**Clôture de la phase 6** : CI verte sur `main`, toutes les tâches (API, interface, parcours, pile Docker).

---

<a id="phases-cloturees"></a>
## Phases clôturées

<a id="phase-1"></a>
## Phase 1 — Mécanique commune des secteurs

**Objectif** : tout ce qu'un secteur réutilise, construit une fois, testé avec un secteur factice.
**Pourquoi** : sans ce socle, chaque secteur referait le catalogue, la consigne et le remplacement des sources.
**Résultat de phase** : un secteur factice complet bascule depuis Réglages, avec ses sources, sa consigne et ses autorités. La tech est intacte.

<a id="lot-1-1"></a>
### Lot 1.1 — Le catalogue d'un secteur

- **Objectif** : chaque secteur a un fichier de catalogue lisible, chargé avec le secteur.
- **À faire**
  - Un fichier par secteur dans `data/sectors/` : sources RSS (nom, adresse, domaine, rang de confiance), requêtes GDELT et Google News, autorités, profil.
  - Pour la tech, le catalogue reprend les 31 flux et les 4 dépôts actuels, sans changement.
  - Le registre des secteurs charge et valide ces fichiers : un domaine inconnu ou une adresse mal formée sont refusés.
- **Dépend de** : rien.
- **Tests du lot** : chargement et refus d'un catalogue invalide ; le catalogue tech donne les mêmes sources qu'avant.
- **Résultat attendu** : `uv run pytest` vert, et le catalogue tech listé à l'identique dans l'écran Sources.
- **Fait (2026-11-22)** : un fichier par secteur dans `data/sectors/`. Celui de la tech renvoie à la configuration d'exemple (`sources_from`), qui reste sa seule liste : 31 flux, 4 dépôts. Le chargeur refuse un profil inconnu, une catégorie d'un autre secteur, une adresse mal formée, un domaine ou un rang de confiance invalides. **En plus du prévu** : le serveur refuse de basculer vers un secteur sans catalogue utilisable (422 « sector not ready »), avant d'écrire la configuration ; l'image Docker embarque `data/sectors/`. Preuve : 12 tests nouveaux (`tests/test_sector_catalog.py`, `tests/test_sectors.py`) ; les recommandations tech de l'écran Sources sont identiques (test). Suite : 942 tests verts, 1 échec ancien sans lien (voir « Points à confirmer »).

<a id="lot-1-2"></a>
### Lot 1.2 — Le profil éditorial d'un secteur

- **Objectif** : chaque secteur a sa consigne pour l'IA (ce qui compte, comment noter l'importance).
- **À faire**
  - Le secteur nomme son profil par défaut ; le changement de secteur le pose dans la configuration.
  - Un règlement commun à tous les profils hors tech : jamais de conseil (investissement, juridique, médical), et seulement ce que la source dit.
- **Dépend de** : 1.1.
- **Tests du lot** : la consigne envoyée à l'IA contient le profil du secteur et la règle « pas de conseil ».
- **Résultat attendu** : après un changement vers le secteur factice, le profil par défaut de la configuration est le sien.
- **Fait (2026-11-22)** : le secteur porte ses règles (`rules`) ; hors tech, la règle « jamais de conseil, seulement ce que la source dit » s'ajoute à la consigne d'analyse et aux deux consignes d'écriture. Le changement de secteur pose le profil du catalogue comme profil par défaut. Les consignes tech restent identiques au caractère près (test). Preuve : `tests/test_sector_prompts.py` (3 tests), `tests/test_sectors.py`.

<a id="lot-1-3"></a>
### Lot 1.3 — Les autorités du secteur, sources officielles

- **Objectif** : un communiqué d'une autorité du secteur (AMF, CNIL…) est reconnu comme source officielle.
- **À faire**
  - Le registre de confiance ajoute les autorités du secteur actif à sa liste intégrée.
  - Ce que la configuration fixe (`reliability.domains`) garde le dernier mot.
- **Dépend de** : 1.1.
- **Tests du lot** : une news d'une autorité du secteur factice reçoit le rang officiel ; hors du secteur, elle ne le reçoit pas.
- **Résultat attendu** : l'étiquette « Confirmé » est possible pour une annonce d'autorité.
- **Fait (2026-11-22)** : `ReliabilityPolicy.for_config` : liste intégrée, puis autorités du secteur actif, puis `reliability.domains` qui garde le dernier mot ; utilisé partout où la politique était construite (API, pipeline, CLI, évaluation). Un communiqué d'autorité confirmé reçoit « Confirmé » dans son secteur, pas ailleurs. Preuve : `tests/test_sector_authorities.py` (6 tests).

<a id="lot-1-4"></a>
### Lot 1.4 — Changer de secteur remplace les sources

- **Objectif** : basculer de secteur installe ses sources et désactive les autres, sans rien supprimer.
- **À faire**
  - Commencer par la sauvegarde : la copie de la configuration existe déjà (lot 47), le vérifier dans le test.
  - Chaque source ajoutée par un catalogue est marquée de son secteur ; une source sans marque est tech.
  - Au changement : les sources des autres secteurs sont désactivées, celles du nouveau sont ajoutées ou réactivées. Au retour, les anciennes reviennent.
  - Réglages montre, avant la confirmation, le nombre de sources ajoutées et désactivées.
- **Dépend de** : 1.1.
- **Tests du lot** : aller-retour tech → factice → tech, sources identiques au départ ; une source ajoutée à la main n'est jamais supprimée.
- **Résultat attendu** : dans l'écran Sources, après la bascule, seules les sources du secteur sont actives.
- **Fait (2026-11-22)** : `lucidnews/sector_switch.py`. Flux RSS, pages et dépôts marqués par secteur ; ceux des autres secteurs désactivés avec `disabled_by_sector`, ceux du secteur réactivés, ceux du catalogue ajoutés. Les sources uniques (Hacker News, Reddit, GDELT…) sont mises de côté par secteur (`sources.parked`) et rendues au retour. Une source ajoutée à la main dans un secteur en porte la marque. Aperçu sans écriture : `GET /api/settings/sector/preview` ; la fenêtre de confirmation affiche les nombres et refuse un secteur pas prêt. Preuve : `tests/test_sector_switch.py` (6 tests, dont l'aller-retour identique), `tests/test_sectors.py`, `SectorCard.test.tsx`.

<a id="lot-1-5"></a>
### Lot 1.5 — Vérifier une source avant de la cataloguer

- **Objectif** : un outil dit, pour chaque source d'un catalogue, si elle est vivante et utilisable.
- **À faire**
  - Une commande lit chaque source pour de vrai : adresse en HTTPS, flux lisible, news de moins de 30 jours, titres et liens présents.
  - Elle écrit un rapport daté, source par source : gardée, écartée, et pourquoi.
  - La CI ne lance pas cette commande, car elle dépend du réseau ; un test la vérifie sur des flux factices.
- **Dépend de** : 1.1.
- **Tests du lot** : flux valide, flux mort, flux trop ancien, adresse en HTTP, chacun classé comme il faut.
- **Résultat attendu** : la commande, lancée sur le catalogue tech, donne un rapport lisible.
- **Fait (2026-11-22)** : commande `lucidnews-sources-check <secteur> [--out]` : HTTPS, réponse 200, flux lisible, news titrées avec lien, plus récente de moins de 30 jours ; rapport Markdown daté. Lancée en vrai sur la tech : 26 flux gardés sur 30, 4 sans publication depuis 46 à 263 jours (rapport : `docs/sources/verification/tech-2026-11-22.md`) ; le catalogue tech n'est pas modifié par ce chantier. Preuve : `tests/test_source_check.py` (4 tests).

<a id="lot-1-6"></a>
### Lot 1.6 — Lire une source qui n'a pas de flux RSS

- **Objectif** : une autorité qui publie une page de communiqués sans flux RSS devient une source.
- **Décidé (22/11/2026, décision 7)** : un lecteur de pages de liste, limité aux sites officiels et publics. Il respecte `robots.txt` (règles d'accès posées par le site) et lit lentement. L'outil 1.5 détecte quand une page change de forme.
- **À faire** : un lecteur configuré par site (adresse de la liste, sélecteur des liens), qui respecte `robots.txt`, avec un délai entre deux pages ; il passe par la vérification 1.5.
- **Dépend de** : 1.5.
- **Tests du lot** : une page de liste enregistrée donne ses news ; une page interdite par `robots.txt` n'est pas lue.
- **Résultat attendu** : une page d'autorité factice devient une source comme une autre.
- **Fait (2026-11-22)** : `sources.pages` et `lucidnews/scrapers/pages.py`. `robots.txt` lu d'abord, une requête par page et par run, pause entre deux sites, HTTPS obligatoire, liens du même site seulement, dates françaises ou anglaises ; un bloc sans date est ignoré (sinon un communiqué reviendrait comme neuf à chaque run). Une page est clé `rss/<nom>` : santé, archive et édition la traitent comme un flux ; le vérificateur 1.5 la juge aussi. Preuve : `tests/test_page_sources.py` (7 tests), `tests/test_sector_switch.py`.

<a id="lot-1-7"></a>
### Lot 1.7 — Une interface neutre

- **Objectif** : plus aucun texte qui dit « tech » hors du secteur tech.
- **À faire**
  - La page de connexion dit le secteur de l'installation. La lecture du secteur est ouverte sans session, sans rien de privé.
  - Relire les textes de l'interface qui disent « tech » ou « IT ».
  - Respecter la charte : jetons de design, vérification ordinateur et téléphone.
- **Dépend de** : 1.4.
- **Tests du lot** : la page de connexion affiche le nom du secteur factice ; aucun texte « tech » hors du secteur tech (test sur les traductions).
- **Résultat attendu** : en secteur factice, la page de connexion parle de ce secteur.
- **Fait (2026-11-22)** : `GET /api/sector` lisible sans session (nom, domaines, rien de privé) ; chaque secteur a un nom court (`nouns`). La page de connexion dit « La veille {secteur} à laquelle on peut se fier. » ; exemples neutres ; « domaines IT » devient « domaines ». Un test garde les traductions sans « tech » ni « IT » hors noms de secteurs et de catégories. Vu dans le navigateur, ordinateur et téléphone : connexion, carte Secteur, fenêtre de confirmation. Preuve : `i18n.sector.test.ts`, `AuthPage.test.tsx` (2 tests), `tests/test_sectors.py`.

**Clôture de la phase 1** : `uv run pytest`, `npm run lint`, `format:check`, `typecheck`, `npm test`, `npm run build`, `npm run e2e`. Parcours réel : bascule tech → factice → tech dans Réglages, sur l'application compilée.

**Clôturée (2026-11-22)** : 970 tests Python verts ; interface : lint sans erreur (2 avertissements anciens), format, types, 181 tests verts, build ; 6 parcours Playwright verts sur l'application compilée, dont le nouveau parcours réel « un administrateur bascule tech → secteur d'essai → tech, les sources suivent » (secteur d'essai présent seulement sur le serveur de test jetable). Pile Docker reconstruite et saine. **En plus du prévu** : l'image Docker ne contenait pas `data/sectors/` (exception mal écrite, puis dossier caché par un volume anonyme déclaré sur `/app/data`) : corrigé dans `.dockerignore` et `Dockerfile` ; le test `test_3xx_redirect_prints_warning` ne dépend plus du réseau.

---

<a id="phase-0"></a>
## Phase 0 — Socle multi-secteurs (lot 47)

**Objectif** : la tech devient un secteur parmi d'autres, sans changement visible.
**Résultat de phase** : Réglages montre la carte « Ce que couvre la veille » ; les catégories viennent du serveur.

**Clôturée (30/10/2026)** : 931 tests Python, 177 tests d'interface, 5 parcours Playwright verts ; carte vérifiée dans le navigateur sur l'application compilée, aucune erreur. Détail : [journal des lots](../lots.md#lot-47--secteurs--le-socle).

---

<a id="actions"></a>
## Actions de l'utilisateur

| Quand | Action |
|---|---|
| Avant la phase 1 | Trancher D1 à D5 — **fait le 22/11/2026** |
| Fin de chaque lot | Commiter et pousser sur `dev` avec le libellé proposé |
| Avant chaque run réel (2.4, 3.4, 4.4, 5.4) | Avoir une clé d'IA avec du quota, dans `.env` (Claude ne la lit ni ne l'écrit) |
| Lots 2.5, 3.5, 4.5, 5.5 | Relire l'édition du secteur et donner ton accord |
| Lot 6.3 | Dire « version validée », puis pousser `main` |

---

<a id="a-confirmer"></a>
## Points à confirmer

| # | Point | Quand | Pourquoi |
|---|---|---|---|
| — | Flux RSS publics des autorités | Lots 2.3, 3.3, 4.3, 5.3 | Vérifiés flux par flux par l'outil 1.5 |
| ~~—~~ | ~~Le test `test_3xx_redirect_prints_warning` échoue en local~~ | — | **Réglé le 22/11/2026** : le test ne dépend plus du DNS |

---

<a id="auto"></a>
## Décidé automatiquement

| Sujet | Choix | Pourquoi |
|---|---|---|
| Une phase commune avant les secteurs | Phase 1 | Catalogue, consigne, autorités et bascule servent aux quatre secteurs |
| Tests de la mécanique | Un secteur factice | On teste la bascule sans attendre un vrai secteur |
| Préfixe des identifiants | `finance-`, `legal-`, `health-`, `energy-` | Les identifiants doivent être uniques entre secteurs |
| Sources payantes | Écartées | Un flux tronqué ou payant ne permet pas de vérifier la news |
| Taille d'un catalogue | 15 à 25 sources | Assez pour couvrir chaque domaine sans noyer l'IA |
| Règle « pas de conseil » | Dans chaque profil hors tech | Finance, droit et santé sont des métiers réglementés |
| Numérotation | Phases 0 à 6 ici ; le journal des lots garde « lot 47 » pour la phase 0 | Aucune référence existante ne casse |

---

<a id="zone-technique"></a>
## Zone technique concernée

- **Secteurs** : `lucidnews/sectors.py`, `lucidnews/sector_catalog.py` (lot 1.1), `lucidnews/taxonomy.py`, `lucidnews/models.py` (`Config.sector`), `data/sectors/tech.json`, `.dockerignore`
- **API** : `lucidnews/web_api.py` (`GET /api/sector`, `PUT /api/settings/sector`), `lucidnews/settings_api.py`
- **Sources** : `lucidnews/source_catalog.py`, `lucidnews/sector_switch.py` (1.4), `lucidnews/source_check.py` et la commande `lucidnews-sources-check` (1.5), `lucidnews/scrapers/pages.py` et `sources.pages` (1.6), `lucidnews/source_health.py`, `lucidnews/pipeline/collect.py`, `lucidnews/scrapers/` (`rss.py`, `gdelt.py`, `google_news.py`), `data/config.example.json`, `data/presets.json`, `docs/sources/verification/`
- **IA** : `lucidnews/ai/prompting/analysis.py` et `enrichment.py` (règles du secteur, 1.2), `lucidnews/ai/analyzer.py`, `lucidnews/ai/enricher.py`, `profiles/` (nouveaux profils par secteur)
- **Fiabilité** : `lucidnews/reliability/registry.py`, `lucidnews/reliability/assess.py` (`ReliabilityPolicy.for_config`, 1.3)
- **Interface** : `frontend/src/features/settings/SectorCard.tsx`, `frontend/src/features/auth/AuthPage.tsx`, `frontend/src/features/edition/domains.ts`, `frontend/src/lib/sector.ts`, `frontend/src/lib/i18n.ts`
- **Tests** : `tests/test_sectors.py`, `test_sector_catalog.py`, `test_sector_prompts.py`, `test_sector_authorities.py`, `test_sector_switch.py`, `test_source_check.py`, `test_page_sources.py`, `frontend/e2e/journeys.spec.ts`, `scripts/e2e_server.py` (secteur d'essai), `frontend/src/features/settings/SectorCard.test.tsx`, `frontend/src/lib/i18n.sector.test.ts`
- **Docker** : `Dockerfile` (volume `/data` seulement), `.dockerignore`
- **Documentation** : `docs/lots.md`, `docs/architecture.md`, `README.md`, `Plan.md`
