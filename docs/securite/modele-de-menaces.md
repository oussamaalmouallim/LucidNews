# Modèle de menaces — LucidNews

Établi le 17 octobre 2026 (lot 30). À relire à chaque lot qui ajoute une porte d'entrée.
Rapport d'audit associé : [audit-securite-2026-10.html](audit-securite-2026-10.html).

## Ce qu'on protège

| Bien | Pourquoi il compte |
|---|---|
| Comptes (e-mail, nom, empreinte du mot de passe, sessions) | Données personnelles ; une prise de compte administrateur donne la main sur la veille. |
| Abonnés de la newsletter (e-mail, préférences) | Données personnelles, liste revendable. |
| Préférences des lecteurs | Données personnelles (centres d'intérêt). |
| Configuration et clés d'API (IA, Resend, Google) | Coût direct et usurpation si elles fuient. |
| Intégrité de la veille (sources, étiquettes de fiabilité) | L'argument de vente : une étiquette falsifiée trompe tous les lecteurs. |
| Disponibilité de l'API | Sans elle, plus d'édition. |

## Les portes d'entrée

| Porte | Qui l'atteint | Garde |
|---|---|---|
| `/api/auth/*` (connexion, inscription, Google, compte) | Tout le monde | Limites par client et par adresse, scrypt, origine vérifiée, PKCE + state + nonce |
| 6 routes de lecture (éditions, news, recherche, santé) | Comptes connectés | Session ; limite par client, recherche et période à un cinquième |
| Routes d'administration (réglages, sources, qualité, abonnés, runs) | Rôle admin | Refus par défaut pour tout autre rôle, origine vérifiée sur les écritures |
| Service public (`lucidnews-public` : confirmation, désabonnement) | Tout le monde | Jetons signés, CSP stricte, jetons jamais journalisés |
| Flux collectés (RSS, Hacker News, Reddit, GitHub…) | Quiconque publie un flux | Adresses validées en http(s), garde anti-adresses internes, React échappe tout |
| Fournisseurs IA | Le fournisseur | Réponses validées par pydantic ; aucune exécution de leur contenu |
| Serveur MCP (`lucidnews-mcp`) | Processus local en stdio | Pas exposé sur le réseau |

## Les attaquants retenus

| Profil | Ce qu'il veut | Ce qui l'arrête |
|---|---|---|
| Visiteur non connecté | Essayer des mots de passe, bloquer les connexions, savoir qui est inscrit | Limites par client (vraie IP derrière le proxy), mots de passe courants refusés, inscriptions fermables |
| Lecteur connecté | Lire l'administration, les abonnés, les préférences d'autrui ; saturer le serveur | Refus par défaut, aucune route ne nomme un autre compte, limite de requêtes |
| Site tiers malveillant | Faire agir le navigateur d'un connecté (CSRF) | Origine vérifiée, corps JSON obligatoire, cookie SameSite=Lax |
| Éditeur d'un flux piégé | Injecter du script, faire appeler une adresse interne | Échappement React, CSP, validation http(s), garde SSRF |
| Personne qui récupère un cookie ou un journal | Se faire passer pour un lecteur, lire ses recherches | Sessions fermées à 90 jours au plus, déconnexion côté serveur, journaux sans paramètres |
| Dépendance compromise ou vulnérable | Exécuter du code dans l'application | Verrou des versions (uv.lock, package-lock), pip-audit et npm audit dans la CI à chaque push |

## Risques acceptés (et jusqu'à quand)

| Risque | Pourquoi accepté | Revu au |
|---|---|---|
| L'inscription dit si une adresse est prise | Pas d'e-mail de vérification pour l'instant | Lot 33 |
| Mots de passe comparés à une liste courte, pas à une base de fuites | Pas d'envoi vers un tiers | Après la bêta |
| Compteurs de limites en mémoire (perdus au redémarrage, une seule instance) | Un seul serveur prévu | Lot 46 (plusieurs instances) |
| Pas de HSTS ni de frame-ancestors côté application | Ils relèvent du reverse proxy | Lot 32 |
