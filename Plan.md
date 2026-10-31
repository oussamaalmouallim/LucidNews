# Plan — LucidNews jusqu'au lancement commercial

Mis à jour le 17 octobre 2026 (lot 27 clôturé, décisions du 17 octobre). Plan établi le 13 octobre 2026, après l'étude de marché et l'audit du code
(rapport : [docs/etude-marche/rapport-lucidnews-2026-10.html](docs/etude-marche/rapport-lucidnews-2026-10.html)).

L'historique complet des lots 0 à 26 reste dans [docs/lots.md](docs/lots.md). Ce fichier fixe
ce qui reste à faire, dans l'ordre, avec des critères mesurables.

## Le produit à lancer (V1)

- **Une veille tech éditée, partagée, personnalisée par lecteur.** Un pipeline par domaine,
  commun à tous ; chaque lecteur règle sa newsletter (domaines, fréquence, niveau de détail,
  langue). Le coût IA est mutualisé : environ 3 000 tokens par news, quel que soit le nombre
  de lecteurs (mesuré sur le run du 11 octobre 2026 : 99 274 tokens pour 33 news).
- **Argument de vente : la confiance mesurée.** Étiquette Confirmé / Fiable / Non vérifié /
  Rumeur sur chaque news, corroboration, méthode publique, taux d'erreur publié.
- **Bilingue FR/EN.** Le créneau francophone de la veille tech est peu servi (TLDR est en
  anglais seulement).
- **Hors V1** : sources personnelles par utilisateur, veille concurrentielle d'entreprise,
  équipes, application mobile, paiement en ligne (voir « Décisions »).

## État au 17 octobre 2026

| Domaine | État | Écart avant la vente |
|---|---|---|
| Collecte, doublons, sélection | ✅ opérationnel | — |
| Fiabilité et corroboration | ✅ opérationnel | Taux d'erreur non mesuré (lot 12) |
| IA (facultative, budget, quota) | ✅ opérationnel | Suivi mensuel des coûts |
| Newsletter (quotidienne, hebdo, aperçu, opt-in, désabonnement) | ✅ code prêt | Aucun envoi réel vérifié, rebonds non gérés |
| Application web (édition, archive, recherche, sources, qualité, réglages) | ✅ opérationnel | — |
| Comptes (e-mail, Google OAuth, sessions, rôles, page Mon compte) | ✅ sans e-mail | Vérification d'adresse et mot de passe oublié par e-mail reportés (lot 33) |
| Exécution serveur | ❌ | Planification macOS uniquement (launchd), interface non servie en production |
| Données | 🟡 SQLite × 3 | Ni WAL, ni sauvegarde automatique |
| Observabilité | ❌ | Ni suivi d'erreurs ni disponibilité |
| Conformité | ❌ | Ni confidentialité, ni CGU, ni CNDP |
| Tests | ✅ 905 Python, 173 interface | Ni bout en bout ni intégration continue |

## Phase A — Finalisation fonctionnelle

### Lot 27 — Rôles et isolation des comptes · ✅ clôturé le 17 octobre 2026

Détail de la réalisation : [docs/lots.md](docs/lots.md#lot-27--rôles-et-isolation-des-comptes).
Critères atteints : 403 pour un lecteur sur 100 % des 36 requêtes d'administration, inventaire
des routes lu dans le code de l'API, isolation des préférences testée, suites au vert.

- Rôles `admin` (opérateur) et `reader` (lecteur). Le premier compte créé en terminal
  (`lucidnews-users add --admin`) est administrateur.
- Pages et routes d'administration (Réglages, Sources, Qualité, Abonnés, runs, planification)
  réservées au rôle `admin`. Elles ne dépendent plus de l'écoute en local (`is_loopback`), qui
  ne tient pas derrière un reverse proxy.
- Un lecteur ne voit et ne modifie que ses propres données.
- **Critères** : un test parcourt toutes les routes et vérifie 403 pour un lecteur sur 100 % des
  routes d'administration ; un lecteur ne peut pas lire les préférences d'un autre (test) ;
  aucune régression (suites Python et interface au vert).
- **Dépend de** : lot 26 (comptes).

### Lot 27 bis — Édition rangée par domaine · ✅ clôturé le 17 octobre 2026

Demande du 17 octobre : une section par domaine de l'IT (IA, Développement, Cloud…), interface
soignée. Détail : [docs/lots.md](docs/lots.md#lot-27-bis--édition-rangée-par-domaine).

### Lot 28 — Compte en libre-service, sans e-mail · ✅ clôturé le 17 octobre 2026

Revu le 17 octobre 2026 : **ni vérification d'e-mail ni envoi d'e-mails pour le moment**.

- Page « Mon compte » : nom, changement du mot de passe (demande l'ancien, ferme les autres
  sessions), liste et fermeture des sessions ouvertes.
- Suppression du compte et export des données (JSON) depuis l'application : droits des
  personnes (loi 09-08, RGPD).
- Mot de passe oublié : sans e-mail, réinitialisation par un administrateur
  (`lucidnews-users passwd`, déjà disponible) ; le lien par e-mail attend le lot 33.
- **Critères** : chaque parcours a un test ; un mot de passe changé ferme les autres sessions
  (test) ; un compte supprimé ne peut plus se connecter et ses sessions disparaissent (test) ;
  l'export ne contient jamais de hachage de mot de passe ni de jeton (test).
- **Dépend de** : lot 27 ✅.
- **Reporté au lot 33** : vérification de l'adresse et mot de passe oublié par e-mail.

### Lot 29 — Préférences du lecteur et veille personnelle · ✅ clôturé le 17 octobre 2026

Revu le 17 octobre 2026 (pas d'envoi d'e-mails pour le moment) :

- Le lecteur règle, depuis son compte, ses domaines, son niveau de détail, sa langue et s'il
  veut voir les news non confirmées. Les préférences sont liées au compte (l'écran Abonnés reste
  l'outil de l'administrateur).
- L'Édition propose « Ma sélection » : l'édition du jour filtrée par ses préférences, rangée par
  domaine comme le reste.
- L'envoi par e-mail de cette sélection (newsletter) attend le lot 33.
- **Critères** : parcours testé (connexion → préférences → Ma sélection) ; un lecteur ne lit ni ne
  modifie les préférences d'un autre (test) ; sans préférence, l'édition complète s'affiche.
- **Dépend de** : lots 27 et 28.

## Phase B — Tests et sécurité

### Lot 30 — Sécurité applicative · ✅ clôturé le 17 octobre 2026

Rapport : [docs/securite/audit-securite-2026-10.html](docs/securite/audit-securite-2026-10.html). Critères atteints : ASVS niveau 1 documenté ([liste](docs/securite/asvs-niveau-1.md)), 0 vulnérabilité connue (pip-audit, npm audit), modèle de menaces écrit ([document](docs/securite/modele-de-menaces.md)).

- Liste OWASP ASVS niveau 1, en-têtes de sécurité et CSP sur l'interface servie, limitation de
  débit sur l'API, audit des dépendances (`pip-audit`, `npm audit`), modèle de menaces écrit.
- **Critères** : ASVS niveau 1 couvert et documenté ; 0 vulnérabilité haute ou critique ouverte.

### Lot 31 — Tests de bout en bout et intégration continue · ✅ clôturé le 18 octobre 2026

- Parcours Playwright sur un serveur de test : inscription, connexion,
  préférences, aperçu, déconnexion, accès refusé à l'administration. (La vérification de
  l'adresse est reportée avec l'e-mail au lot 33.)
- GitHub Actions : pytest, vitest, lint, format, build, Playwright.
- **Critères** : CI verte sur chaque push ; une régression volontaire fait échouer la CI.

Réalisé : 5 parcours Playwright sur l'interface compilée devant une API jetable
(`scripts/e2e_server.py`), CI GitHub Actions en trois tâches (API, interface, parcours) avec
pip-audit et npm audit. Une régression volontaire (un lecteur autorisé sur les réglages) fait
échouer un parcours et 3 tests Python. CI verte sur GitHub : à confirmer au premier push.

### Lot 12 bis — Preuve de qualité (action humaine + outil existant)

- Annoter au moins 100 news dans l'écran Qualité, mesurer avec `lucidnews-eval`.
- **Critères** : taux de « faux fiables » mesuré et publié sur une page « Méthode » ;
  objectif < 5 % avant la communication commerciale.

## Phase C — Préparation de la production

### Lot 32 — Exécution serveur · ✅ clôturé le 18 octobre 2026

- `docker compose` : API, pipeline planifié (cron du conteneur ou minuterie systemd, pas
  launchd), service public, Caddy (HTTPS, interface compilée servie, `/api` relayé).
- SQLite en mode WAL avec délai d'attente ; vérification de santé de chaque service.
- La planification depuis l'interface pilote le planificateur serveur.
- **Critères** : un serveur vierge démarre tout avec une commande ; un run planifié se
  déclenche à l'heure et apparaît dans l'historique ; redémarrage sans perte.

Réalisé et vérifié en vrai avec Docker (projet isolé, volume jeté après) : démarrage en une
commande, run planifié déclenché à l'heure choisie depuis l'API et terminé en succès, historique
et compte conservés après arrêt et redémarrage, aucun second déclenchement après redémarrage,
HTTPS local avec HSTS. Le service public est écarté tant que l'e-mail l'est (lot 33).

### Lot 33 — E-mail en production · **reporté (décision du 17 octobre 2026)**

Reprend aussi la vérification de l'adresse et le mot de passe oublié par e-mail (retirés du lot 28).

- Domaine d'envoi authentifié (SPF, DKIM, DMARC), adresse postale de l'expéditeur dans le
  pied de page, webhooks Resend : rebonds et plaintes désinscrivent automatiquement.
- **Critères** : premier envoi réel reçu en boîte de réception chez Gmail et Outlook ; un
  rebond simulé désactive l'adresse (test) ; taux de plaintes suivi.

### Lot 34 — Données

- Sauvegarde à chaud des trois bases SQLite, chiffrée, hors serveur, chaque jour ;
  restauration documentée.
- Décision PostgreSQL écrite (voir « Décisions »).
- **Critères** : restauration testée de bout en bout en moins de 30 minutes ; 7 sauvegardes
  quotidiennes et 4 hebdomadaires conservées.

### Lot 35 — Observabilité et coûts

- Suivi d'erreurs (GlitchTip auto-hébergé ou offre gratuite), sonde de disponibilité externe,
  coût IA par mois à partir des tokens archivés, alerte de budget.
- **Critères** : une erreur provoquée remonte en moins de 5 minutes ; alerte si le coût IA du
  mois dépasse le budget fixé.

### Lot 36 — Conformité

- Politique de confidentialité, CGU, mentions légales, page « Sources et attribution »,
  procédure de retrait pour un éditeur.
- Déclaration CNDP (loi 09-08) et, si l'hébergement est hors du Maroc, autorisation de
  transfert. Accords de traitement avec Resend, Google et l'hébergeur.
- **Critères** : pages publiées et liées depuis chaque page et chaque e-mail ; dossier CNDP
  déposé ; avis d'un juriste sur les résumés (droit voisin de la presse dans l'UE).

## Phase D — Hébergement et déploiement · **reportée (décision du 17 octobre 2026)**

On finit d'abord l'application (phases A, B et C). Le choix de l'hébergeur et la mise en ligne
seront décidés après. Les lots de la phase C se préparent et se vérifient en local (Docker
Compose sur la machine de développement) ; seuls les points qui exigent un domaine réel (envoi
authentifié du lot 33) attendent l'hébergement.

### Lot 37 — Hébergement

- VPS (recommandé : environ 2 vCPU et 4 Go de RAM), domaine, HTTPS, pare-feu, accès SSH par
  clé, préproduction.
- Déploiement en une commande depuis la CI, retour arrière à la version précédente.
- **Critères** : déploiement et retour arrière testés ; coût mensuel mesuré, objectif
  ≤ 15 € pendant la bêta.

### Lot 38 — Bêta privée

- 20 à 50 lecteurs pendant 4 semaines, inscriptions sur invitation (`allow_signup` fermé).
- **Critères** : taux d'ouverture, de désabonnement et de rétention à 4 semaines mesurés ;
  10 entretiens ; décision écrite sur les prix et sur l'arabe.

## Phase F — Nouveaux secteurs (décision du 30 octobre 2026)

Ouvrir LucidNews à d'autres métiers que la tech. Un secteur par installation, choisi dans Réglages.

- **Lot 47 — Socle** · ✅ clôturé le 30 octobre 2026 ([détail](docs/lots.md#lot-47--secteurs--le-socle)).
- **Lot 48 — Finance** : marchés, banques, assurance, crypto-actifs, fusions-acquisitions, macroéconomie, régulation financière, fintech. Autorités : AMF, ACPR, Banque de France, BCE, ESMA, SEC.
- **Lot 49 — Juridique et réglementaire** : législation, jurisprudence, droit des affaires, droit du travail, données personnelles, droit européen, conformité. Sources : Légifrance, EUR-Lex, Conseil d'État, Cour de cassation, CNIL.
- **Lot 50 — Santé et pharma** : réglementation, essais cliniques, médicaments, dispositifs médicaux, santé publique, e-santé. Autorités : HAS, ANSM, EMA, OMS, FDA.
- **Lot 51 — Énergie et climat** : marchés de l'énergie, renouvelables, efficacité énergétique et CEE, réglementation, climat et RSE. Autorités : CRE, ADEME, ministère de la Transition écologique, AIE.
- **Chaque lot** : catégories, consigne éditoriale, 15 à 25 sources fiables vérifiées une à une (flux réellement lus), autorités dans le registre de confiance, libellés FR/EN et icônes, run réel qui produit une édition.
- **Critères** : changer de secteur dans Réglages remplace les sources (anciennes désactivées, pas supprimées) ; le premier run du nouveau secteur produit une édition rangée par ses catégories ; la tech reste identique (suites au vert).

## Phase E — Après le lancement

Dans l'ordre proposé. Chacun reste à confirmer par les résultats de la bêta.

1. **Lot 39 — Fil d'un événement** : une page par histoire (sources, chronologie, ce qui est
   nouveau, évolution de l'étiquette). Différenciant ; les données existent.
2. **Lot 40 — Synthèse hebdo des tendances** d'un domaine.
3. **Lot 41 — Alertes et suivi d'entités** (entreprise, produit, CVE), par e-mail ou Slack.
4. **Lot 42 — Offres et paiement** : limites Gratuit / Premium, prestataire selon l'entité
   juridique ; d'ici là, pilotes B2B facturés par virement.
5. **Lot 43 — Équipes** : espace partagé, envoi Slack ou Teams, facturation par place.
6. **Lot 44 — Sources personnelles** par utilisateur (offre Pro, coût IA par utilisateur).
7. **Lot 45 — Arabe**, seulement si la bêta le justifie.
8. **Lot 46 — PostgreSQL et plusieurs instances**, seulement si la charge l'exige.

## Dépendances

```
27 Rôles ──► 28 Compte ──► 29 Newsletter libre-service
   │
   │            33 E-mail prod (reporté : vérification, mot de passe oublié, envoi réel)
   └──► 30 Sécurité ──► 31 E2E + CI
32 Exécution serveur ──► 34 Données ──► 37 Hébergement ──► 38 Bêta ──► Phase E
35 Observabilité, 36 Conformité ──► 38 Bêta
12 bis Preuve de qualité ──► communication commerciale
```

## Décisions

| Sujet | Décision proposée | Raison |
|---|---|---|
| Modèle produit | ✅ **Décidé le 17/10** : veille éditée partagée + newsletter personnalisée | Architecture actuelle, coût IA mutualisé |
| PostgreSQL | Pas pour la V1 : SQLite (WAL) + sauvegardes, sur un seul serveur | Une seule instance, peu d'écritures concurrentes ; PostgreSQL si PaaS sans disque ou plusieurs instances |
| Hébergement | **Reporté le 17/10** : finir l'application d'abord. Piste retenue pour plus tard : VPS + Docker Compose + Caddy | Coût fixe et plafonné ; un PaaS coûte environ 2 fois plus avec une facture à l'usage |
| Preuve de qualité | ✅ **Décidé le 17/10** : annoter 100 news (action humaine, écran Qualité) | La fiabilité est l'argument de vente ; elle doit être mesurée avant d'être vendue |
| E-mail | Resend (déjà intégré) | Gratuit jusqu'à 3 000 e-mails par mois, 20 $ pour 50 000 |
| Vérification de l'e-mail | **Reportée le 17/10** : ni vérification ni envoi d'e-mails pour le moment ; à reprendre au lot 33 | Un SaaS ne peut pas envoyer à des adresses non prouvées : à trancher avant tout envoi réel de newsletter |
| Paiement | Reporté (lot 42) | Stripe indisponible pour une société marocaine, CMI sans paiement récurrent (sources secondaires) ; pilotes B2B par virement d'abord |
| Langues | FR + EN au lancement, arabe à tester | Aucune preuve de demande d'arabe pour un public tech |
