# Secteurs de la veille

Une installation LucidNews suit **un secteur**. Le secteur décide de trois choses :

- les domaines de l'édition ;
- la consigne donnée à l'IA ;
- les sources et les autorités reconnues comme officielles.

Ce guide sert à deux personnes :

- l'administrateur, qui choisit le secteur ;
- le développeur, qui en ajoute un.

## Les cinq secteurs

| Secteur | Identifiant | Domaines | Consigne (profil) | Sources vérifiées | Rapport |
|---|---|---|---|---|---|
| Tech et IT | `tech` | 12 | `tech-news` | 31 flux, 4 dépôts GitHub | [tech](sources/verification/tech-2026-11-22.md) |
| Finance | `finance` | 8 | `finance-news` | 26 flux, 1 page officielle | [finance](sources/verification/finance-2026-11-22.md) |
| Juridique et réglementaire | `legal` | 8 | `legal-news` | 16 flux, 4 pages officielles | [juridique](sources/verification/legal-2026-11-22.md) |
| Santé et pharma | `health` | 8 | `health-news` | 20 flux, 2 pages officielles | [santé](sources/verification/health-2026-11-22.md) |
| Énergie et climat | `energy` | 8 | `energy-news` | 21 flux, 4 pages officielles | [énergie](sources/verification/energy-2026-11-22.md) |

Hors tech, chaque consigne porte la même règle : **jamais de conseil** (investissement, juridique, médical), et seulement ce que la source dit. Chaque secteur ajoute ses propres règles :

- **Finance** : une prévision ou un objectif d'analyste n'est jamais un fait.
- **Juridique** : un projet ou une proposition de loi n'est pas une loi.
- **Santé** : une annonce de laboratoire ou une prépublication (étude pas encore relue par des pairs) reste « non vérifiée ».
- **Énergie** : une échéance n'est citée que si la source la donne. Un arrêté publié est confirmé.

## Choisir le secteur (administrateur)

1. Ouvrir **Réglages**, carte « Ce que couvre la veille ».
2. Cliquer « Passer à ce secteur » sur la carte du secteur voulu.
3. Lire la fenêtre de confirmation : elle donne le nombre de sources ajoutées, réactivées et désactivées.
4. Cliquer « Changer ».

Ce qui se passe au changement :

- la configuration est **sauvegardée** avant d'être réécrite ;
- les sources du nouveau secteur sont **ajoutées** ou **réactivées** ;
- celles des autres secteurs sont **désactivées, jamais supprimées** ;
- une source ajoutée à la main reste là, et porte la marque de son secteur ;
- au retour vers un secteur, ses anciennes sources reviennent dans l'état où elles étaient ;
- l'archive reste lisible : une news garde ses domaines, quel que soit le secteur.

Le changement se fait aussi par l'API (`PUT /api/settings/sector`, administrateur). `GET /api/settings/sector/preview?sector=<id>` donne les nombres sans rien écrire.

GDELT (base mondiale d'articles de presse) et Google News sont prêts dans chaque catalogue, mais **désactivés d'office**. Ils font entrer des sites et des conseils qu'on ne contrôle pas. L'administrateur peut les activer dans l'écran Sources.

## Ajouter un secteur (développeur)

Exemple : un secteur `agri`. Les identifiants de ses domaines commencent tous par `agri-`.

### 1. Le secteur et ses domaines

Dans `lucidnews/sectors.py`, écrire une fonction `_agri()` qui renvoie un `Sector`, sur le modèle de `_energy()` :

- `labels`, `nouns` et `descriptions` en français et en anglais ;
- 7 à 8 `SectorCategory`, chacune avec :
  - un identifiant `agri-…` ;
  - ses libellés FR/EN ;
  - sa **portée**, une ligne lue par l'IA ;
  - des alias, c'est-à-dire les mots que l'IA ou une source peuvent employer ;
- `rules=(NO_ADVICE_RULE,)`.

Puis l'ajouter à `SECTORS`. Au chargement, le registre refuse un identifiant de domaine déjà pris par un autre secteur.

Pour un alias, attention : s'il existe déjà, le premier secteur enregistré le garde. Vérifier avec `normalize_categories`, comme le font les tests des secteurs.

Les icônes des domaines vont dans `frontend/src/features/edition/domains.ts`, avec les icônes `lucide-react`. Un domaine sans icône reçoit l'icône générique.

### 2. La consigne pour l'IA

Créer `profiles/agri-news/`, en copiant `profiles/energy-news/` :

| Fichier | Rôle |
|---|---|
| `profile.json` | identifiant, nom affiché, blocs rédigés (`summary`, `background`, `impact`) |
| `match.md` | quelles news relèvent de ce profil, et lesquelles écarter |
| `analysis.md` | la grille de score (0 à 10) et ce qui compte comme confirmé |
| `enrichment.md` | comment rédiger chaque bloc, sans rien inventer |

La règle « jamais de conseil » s'ajoute toute seule aux consignes, par la règle du secteur.

### 3. Le catalogue et les autorités

Créer `data/sectors/agri.json` :

```json
{
  "profile": "agri-news",
  "authorities": { "agriculture.gouv.fr": "official", "terre-net.fr": "reputable" },
  "sources": {
    "rss": [{ "name": "…", "url": "https://…", "category": "agri-…", "profile": "agri-news" }],
    "pages": [{ "name": "…", "url": "https://…", "item_selector": "…", "link_selector": "a", "category": "agri-…", "profile": "agri-news" }],
    "gdelt": { "enabled": false, "query": "…", "category": "agri-…", "profile": "agri-news" },
    "google_news": { "enabled": false, "query": "…", "category": "agri-…", "profile": "agri-news" }
  }
}
```

Les autorités et leur rang :

- **`official`** : les autorités publiques du secteur. Leurs annonces peuvent recevoir l'étiquette « Confirmé ».
- **`reputable`** : la presse sérieuse. Ses news montent au plus à « Fiable ».

Ces rangs complètent le registre de confiance tant que le secteur est actif. Un rang posé dans `reliability.domains` de la configuration garde toujours le dernier mot.

Le chargeur refuse le catalogue entier dans quatre cas : un profil inconnu, une catégorie d'un autre secteur, une adresse mal formée, un rang invalide. Le serveur refuse alors de basculer vers ce secteur (« sector not ready »).

Une **page** sert pour une autorité qui n'a pas de flux RSS. Elle est lue par le lecteur de pages :

- il respecte `robots.txt` (les règles d'accès posées par le site) ;
- il fait une requête par run et ne garde que les liens du même site ;
- il ignore un bloc sans date.

Les réglages d'une page :

| Réglage | Ce qu'il désigne |
|---|---|
| `item_selector` | un bloc de news (sélecteur CSS) |
| `link_selector` | le lien, dans le bloc |
| `date_selector` | la date (`time` par défaut ; l'attribut `datetime` passe en premier) |
| `title_selector` | le titre, quand le lien contient aussi la date ou un chapeau |

### 4. Vérifier chaque source

```bash
uv run lucidnews-sources-check agri --out docs/sources/verification/agri-AAAA-MM-JJ.md
```

Une source est **gardée** si elle remplit toutes ces conditions :

- elle est en HTTPS et répond 200 ;
- son flux ou sa page se lit ;
- ses news ont un titre et un lien ;
- sa news la plus récente a moins de 30 jours.

Sinon, la source est **écartée**, avec la raison. Seules les sources gardées entrent au catalogue. Viser 15 à 25 sources, et au moins une par domaine.

Pour valider la collecte sans IA, travailler sur une copie des données :

1. basculer la copie vers le secteur ;
2. lancer `PipelineOrchestrator(config, storage).fetch_all_sources(since)` avec `ai.enabled` à `false` ;
3. lire `last_fetch_report`, source par source.

### 5. Les tests

Copier `tests/test_energy_sector.py`. Il couvre :

- les domaines, dans l'ordre et dans les deux langues ;
- les mots qui tombent sur les bons domaines, sans voler ceux des autres secteurs ;
- les règles de la consigne ;
- le chargement du catalogue, avec au moins une source par domaine ;
- chaque source « gardée » dans le rapport ;
- le rang officiel des autorités.

Deux tests listent les secteurs et les profils, et sont à compléter :

- `tests/test_sectors.py` ;
- `tests/test_balanced_digest.py` (profils dans l'ordre des dossiers).

Le parcours Playwright « five sectors » de `frontend/e2e/journeys.spec.ts` gagne une étape.

### 6. L'image Docker

`data/sectors/` et `profiles/` sont déjà copiés dans l'image (`.dockerignore`). Reconstruire la pile :

```bash
docker compose up -d --build --wait
```

## Limites connues

- **Pages officielles** : l'écran Sources ne les liste pas encore. Elles basculent avec le secteur, mais ne se désactivent pas une par une depuis l'interface.
- **Sans IA**, une news est rangée par le domaine habituel de sa source.
- **Le vérificateur dépend du réseau**, donc la CI ne le lance pas. Un site peut refuser l'accès un jour (erreur 403) et le rendre le lendemain : relancer avant d'écarter une source.
