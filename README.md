# Leyzen Vault

**Projet:** POC Leyzen Vault – Rotation polymorphe de serveurs web + honeypot HTTP

**Description:**
Ce projet est un Proof-of-Concept (PoC) pour démontrer une infrastructure de serveurs web polymorphes qui tournent de manière aléatoire et éphémère derrière un reverse proxy, avec un honeypot HTTP minimal pour capturer toutes les requêtes externes.

Le PoC inclut :
- Trois serveurs web différents (Nginx, Apache, Lighttpd) avec un contenu HTML stylisé.
- Un reverse proxy (HAProxy) exposant un point unique vers le serveur actif.
- Un orchestrateur Python qui effectue la rotation des serveurs toutes les X secondes.
- Un honeypot HTTP minimal qui logge toutes les requêtes.
- Preuve côté front et back de la rotation des serveurs via headers HTTP uniques et logs.

**Utilisation rapide:**
1. Construire les images Docker des serveurs et du honeypot.
2. Lancer `docker-compose up`.
3. Démarrer l'orchestrateur pour activer la rotation.
4. Vérifier les headers HTTP via `curl -I http://localhost:8080` pour observer la rotation.

**Notes importantes:**
- Ce projet est un PoC local. Toute utilisation sur des cibles externes nécessite autorisation écrite.
- Les logs et containers éphémères permettent de simuler la rotation et la purge de services.
