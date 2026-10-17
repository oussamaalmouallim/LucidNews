# OWASP ASVS 4.0.3 — niveau 1, état au 17 octobre 2026

Revue manuelle du lot 30, chapitre par chapitre. ✅ couvert · 🟡 partiel · ⏳ au lot indiqué · — sans objet.
Les exigences sans objet (pas d'upload de fichier, pas de GraphQL, pas de WebSocket) ne sont pas listées.

| Chapitre | État | Preuve ou reste à faire |
|---|---|---|
| V2.1 Mots de passe | ✅ | 8 à 128 caractères, aucune règle de composition imposée, mots de passe courants refusés (2.1.7, liste locale), changement avec l'ancien mot de passe (2.1.5), collage autorisé. `lucidnews/auth/passwords.py`, `tests/test_security.py`. |
| V2.2 Authentification générale | ✅ | Limites d'essais par client et par adresse (2.2.1), réponse identique compte inconnu / mauvais mot de passe. |
| V2.4 Stockage des mots de passe | ✅ | scrypt (N=2^14, r=8, p=1), sel aléatoire, comparaison à temps constant. |
| V2.5 Récupération | 🟡 | Pas de lien par e-mail (décision du 17/10) : réinitialisation par un administrateur. ⏳ lot 33. |
| V3 Sessions | ✅ | Jeton aléatoire 256 bits, seule son empreinte stockée, cookie HttpOnly + SameSite=Lax (+ Secure en https), nouveau jeton à chaque connexion, déconnexion côté serveur, fin absolue à 90 jours, fermeture des autres sessions au changement de mot de passe. |
| V4 Contrôle d'accès | ✅ | Refus par défaut, rôle vérifié côté serveur sur chaque route, aucune route ne nomme un autre compte. `tests/test_roles.py`, `tests/test_account.py`. |
| V5 Validation et encodage | ✅ | Corps JSON obligatoire et borné (64 Ko), modèles pydantic sans champ en trop, SQL paramétré, React échappe toute sortie, aucun HTML brut injecté. |
| V6 Cryptographie | ✅ | Bibliothèque standard (secrets, hashlib, hmac) ; aucun algorithme maison. |
| V7 Erreurs et journaux | ✅ | Aucune trace d'erreur renvoyée au client ; journaux sans paramètres d'adresse ; jetons et mots de passe jamais journalisés. |
| V8 Protection des données | ✅ | `Cache-Control: no-store` sur l'API, export et suppression du compte, base des comptes en 0600. |
| V9 Communications | ⏳ | HTTPS et HSTS portés par le reverse proxy : lot 32. |
| V10 Code malveillant | ✅ | Aucune exécution de contenu collecté ; dépendances verrouillées. |
| V12 Fichiers | — | Aucun envoi de fichier par les utilisateurs. |
| V13 API | ✅ | Origine vérifiée sur toute écriture, type de contenu JSON imposé, limite de requêtes par client. |
| V14 Configuration | 🟡 | Dépendances sans faille connue (pip-audit, npm audit), en-têtes de sécurité sur l'API, CSP sur l'interface. Automatisation de l'audit des dépendances : ⏳ lot 31. |
