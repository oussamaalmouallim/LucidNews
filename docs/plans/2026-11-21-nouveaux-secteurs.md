# Nouveaux secteurs — finance, juridique, santé, énergie

> Ouvrir LucidNews à quatre métiers en plus de la tech. Chaque installation suit un secteur,
> choisi dans Réglages, avec ses domaines, sa consigne pour l'IA, ses sources fiables et ses
> autorités. Pour les administrateurs qui vendent ou utilisent une veille métier.

| | |
|---|---|
| **Date et version** | 21 novembre 2026, v1 |
| **Auteur** | Claude, pour Oussama |
| **Branche de travail** | `dev` (dépôt perso `oussamaalmouallim/LucidNews`) ; `main` seulement sur validation |
| **État** | 22/11/2026 — Phase 0 clôturée. Décisions D1 à D5 tranchées. Phase 1 (mécanique commune) ouverte : analyse faite, en attente du feu vert pour le lot 1.1. |

---

## Sommaire

- [Le problème et le but](#probleme)
- [Décisions prises](#decisions)
- [Ce qu'on a trouvé](#constats)
- [Comment les morceaux s'emboîtent](#emboitement)
- [Phases non clôturées](#phases-ouvertes)
  - [Phase 1 — Mécanique commune des secteurs](#phase-1) : [1.1](#lot-1-1) · [1.2](#lot-1-2) · [1.3](#lot-1-3) · [1.4](#lot-1-4) · [1.5](#lot-1-5) · [1.6](#lot-1-6) · [1.7](#lot-1-7)
  - [Phase 2 — Secteur Finance](#phase-2) : [2.1](#lot-2-1) · [2.2](#lot-2-2) · [2.3](#lot-2-3) · [2.4](#lot-2-4) · [2.5](#lot-2-5)
  - [Phase 3 — Secteur Juridique et réglementaire](#phase-3) : [3.1](#lot-3-1) · [3.2](#lot-3-2) · [3.3](#lot-3-3) · [3.4](#lot-3-4) · [3.5](#lot-3-5)
  - [Phase 4 — Secteur Santé et pharma](#phase-4) : [4.1](#lot-4-1) · [4.2](#lot-4-2) · [4.3](#lot-4-3) · [4.4](#lot-4-4) · [4.5](#lot-4-5)
  - [Phase 5 — Secteur Énergie et climat](#phase-5) : [5.1](#lot-5-1) · [5.2](#lot-5-2) · [5.3](#lot-5-3) · [5.4](#lot-5-4) · [5.5](#lot-5-5)
  - [Phase 6 — Fin du chantier](#phase-6) : [6.1](#lot-6-1) · [6.2](#lot-6-2) · [6.3](#lot-6-3)
- [Phases clôturées](#phases-cloturees)
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

<a id="lot-1-2"></a>
### Lot 1.2 — Le profil éditorial d'un secteur

- **Objectif** : chaque secteur a sa consigne pour l'IA (ce qui compte, comment noter l'importance).
- **À faire**
  - Le secteur nomme son profil par défaut ; le changement de secteur le pose dans la configuration.
  - Un règlement commun à tous les profils hors tech : jamais de conseil (investissement, juridique, médical), et seulement ce que la source dit.
- **Dépend de** : 1.1.
- **Tests du lot** : la consigne envoyée à l'IA contient le profil du secteur et la règle « pas de conseil ».
- **Résultat attendu** : après un changement vers le secteur factice, le profil par défaut de la configuration est le sien.

<a id="lot-1-3"></a>
### Lot 1.3 — Les autorités du secteur, sources officielles

- **Objectif** : un communiqué d'une autorité du secteur (AMF, CNIL…) est reconnu comme source officielle.
- **À faire**
  - Le registre de confiance ajoute les autorités du secteur actif à sa liste intégrée.
  - Ce que la configuration fixe (`reliability.domains`) garde le dernier mot.
- **Dépend de** : 1.1.
- **Tests du lot** : une news d'une autorité du secteur factice reçoit le rang officiel ; hors du secteur, elle ne le reçoit pas.
- **Résultat attendu** : l'étiquette « Confirmé » est possible pour une annonce d'autorité.

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

<a id="lot-1-6"></a>
### Lot 1.6 — Lire une source qui n'a pas de flux RSS

- **Objectif** : une autorité qui publie une page de communiqués sans flux RSS devient une source.
- **Décidé (22/11/2026, décision 7)** : un lecteur de pages de liste, limité aux sites officiels et publics. Il respecte `robots.txt` (règles d'accès posées par le site) et lit lentement. L'outil 1.5 détecte quand une page change de forme.
- **À faire** : un lecteur configuré par site (adresse de la liste, sélecteur des liens), qui respecte `robots.txt`, avec un délai entre deux pages ; il passe par la vérification 1.5.
- **Dépend de** : 1.5.
- **Tests du lot** : une page de liste enregistrée donne ses news ; une page interdite par `robots.txt` n'est pas lue.
- **Résultat attendu** : une page d'autorité factice devient une source comme une autre.

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

**Clôture de la phase 1** : `uv run pytest`, `npm run lint`, `format:check`, `typecheck`, `npm test`, `npm run build`, `npm run e2e`. Parcours réel : bascule tech → factice → tech dans Réglages, sur l'application compilée.

---

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

<a id="lot-2-2"></a>
### Lot 2.2 — La consigne finance

- **Objectif** : l'IA note une news finance comme un analyste prudent.
- **À faire** : profil `finance-news` (routage, grille de score, rédaction) ; jamais de conseil d'investissement ; un chiffre ou une prévision ne vaut que si la source le donne.
- **Dépend de** : 2.1.
- **Tests du lot** : consigne construite avec le profil finance ; règle « pas de conseil » présente.
- **Résultat attendu** : la consigne finance est lisible dans les tests.

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

<a id="lot-2-4"></a>
### Lot 2.4 — Run réel en finance

- **Objectif** : un vrai run, sur une copie des données, produit une édition finance.
- **À faire** : copie des données dans le dossier temporaire ; bascule en Finance ; run avec l'IA et un budget de tokens (décision 9) ; contrôle des domaines, des étiquettes et des sources ; copie supprimée ensuite.
- **Dépend de** : 2.2, 2.3.
- **Tests du lot** : le run se termine en succès ; aucune news rangée « Autre » par erreur de domaine.
- **Résultat attendu** : capture de l'édition finance, et nombre de news par domaine noté dans le plan.

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

<a id="lot-3-2"></a>
### Lot 3.2 — La consigne juridique

- **Objectif** : l'IA distingue un texte adopté, un projet de texte et un commentaire.
- **À faire** : profil `legal-news` ; une décision ou un texte publié par l'institution compte comme confirmé ; jamais de conseil juridique ; date d'entrée en vigueur citée seulement si la source la donne.
- **Dépend de** : 3.1.
- **Tests du lot** : consigne construite, règles présentes.
- **Résultat attendu** : la consigne juridique est lisible dans les tests.

<a id="lot-3-3"></a>
### Lot 3.3 — Les sources juridiques

- **Objectif** : 15 à 25 sources juridiques vérifiées.
- **À faire** : Légifrance et le Journal officiel, EUR-Lex, Conseil d'État, Cour de cassation, Conseil constitutionnel, CNIL, et des éditeurs juridiques à flux gratuit ; écarter le payant ; passage par l'outil 1.5.
- **Dépend de** : 3.1, 1.5, 1.6.
- **Tests du lot** : catalogue chargé ; rapport sans source écartée.
- **Résultat attendu** : rapport de vérification daté, avec 15 sources gardées ou plus.

<a id="lot-3-4"></a>
### Lot 3.4 — Run réel en juridique

- **Objectif** : un vrai run produit une édition juridique.
- **À faire** : même déroulé que le lot 2.4, en secteur Juridique.
- **Dépend de** : 3.2, 3.3.
- **Tests du lot** : run en succès ; les textes officiels ont le rang officiel.
- **Résultat attendu** : capture de l'édition et chiffres par domaine notés dans le plan.

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

<a id="lot-4-2"></a>
### Lot 4.2 — La consigne santé

- **Objectif** : l'IA traite un résultat d'essai ou une annonce de laboratoire avec prudence.
- **À faire** : profil `health-news` ; jamais de conseil médical ; un résultat non publié ou non évalué reste « non vérifié » ; une autorisation de mise sur le marché compte comme confirmée seulement si l'autorité la publie.
- **Dépend de** : 4.1.
- **Tests du lot** : consigne construite, règles présentes.
- **Résultat attendu** : la consigne santé est lisible dans les tests.

<a id="lot-4-3"></a>
### Lot 4.3 — Les sources santé

- **Objectif** : 15 à 25 sources santé vérifiées.
- **À faire** : HAS, ANSM, ministère de la Santé, Santé publique France, EMA, OMS, FDA, et des revues ou éditeurs à flux gratuit ; passage par l'outil 1.5.
- **Dépend de** : 4.1, 1.5, 1.6.
- **Tests du lot** : catalogue chargé ; rapport sans source écartée.
- **Résultat attendu** : rapport de vérification daté, avec 15 sources gardées ou plus.

<a id="lot-4-4"></a>
### Lot 4.4 — Run réel en santé

- **Objectif** : un vrai run produit une édition santé.
- **À faire** : même déroulé que le lot 2.4, en secteur Santé.
- **Dépend de** : 4.2, 4.3.
- **Tests du lot** : run en succès ; aucune annonce de laboratoire seule n'est « Confirmé ».
- **Résultat attendu** : capture de l'édition et chiffres par domaine notés dans le plan.

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

- **Secteurs** : `lucidnews/sectors.py`, `lucidnews/taxonomy.py`, `lucidnews/models.py` (`Config.sector`), nouveau dossier `data/sectors/`
- **API** : `lucidnews/web_api.py` (`GET /api/sector`, `PUT /api/settings/sector`), `lucidnews/settings_api.py`
- **Sources** : `lucidnews/source_catalog.py`, `lucidnews/sources_cli.py`, `lucidnews/scrapers/` (`rss.py`, `gdelt.py`, `google_news.py`), `data/config.example.json`, `data/presets.json`
- **IA** : `lucidnews/ai/prompting/analysis.py`, `lucidnews/ai/analyzer.py`, `profiles/` (nouveaux profils par secteur)
- **Fiabilité** : `lucidnews/reliability/registry.py`, `lucidnews/reliability/assess.py`
- **Interface** : `frontend/src/features/settings/SectorCard.tsx`, `frontend/src/features/auth/AuthPage.tsx`, `frontend/src/features/edition/domains.ts`, `frontend/src/lib/sector.ts`, `frontend/src/lib/i18n.ts`
- **Tests** : `tests/test_sectors.py`, `frontend/e2e/journeys.spec.ts`, `frontend/src/features/settings/SectorCard.test.tsx`
- **Documentation** : `docs/lots.md`, `docs/architecture.md`, `README.md`, `Plan.md`
