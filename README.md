# Leyzen Vault PoC

## Description

Ce projet est une **preuve de concept pour Leyzen Vault**, un environnement local de documentation et de honeypot simulé, avec une architecture multi-conteneurs Docker orchestrée via `docker-compose` et un orchestrateur Python pour la rotation polymorphe des services Paperless.

Il inclut :

* **Paperless-ngx** : un système de gestion de documents partagé sur 3 conteneurs.
* **Honeypot custom** : pour simuler des attaques et collecter des logs.
* **HAProxy** : pour router le trafic HTTP vers Paperless et le honeypot selon le chemin.
* **Redis et Postgres** : pour Paperless.
* **Volume partagé** : pour que les 3 conteneurs Paperless utilisent le même stockage.
* **Vault Orchestrator** : un script Python qui assure la rotation des conteneurs Paperless tout en gardant la disponibilité.

---

## Architecture

```
          +---------------------+
          |     HAProxy         |
          | (8080 exposé)       |
          +---------------------+
           /                 \
 /honeypot/*                  /*
   |                        (Paperless cluster)
   v
+----------+         +-----------+      +-----------+
| Honeypot |         | Paperless |      | Paperless |
| 5000     |         | web1 8000 |      | web2 8000 |
+----------+         +-----------+      +-----------+
                                   \
                                    +-----------+
                                    | Paperless |
                                    | web3 8000 |
                                    +-----------+
```

---

## Prérequis

* Docker
* Docker Compose
* Git (pour cloner le repo)
* Python

---

## Installation et lancement

1. Cloner le repo :

```bash
git clone git@github.com:3xpyth0n/leyzen-vault.git
cd leyzen-vault
```

2. Construire et démarrer les conteneurs :

```bash
docker-compose up --build -d
```

3. Vérifier l’état des conteneurs :

```bash
docker ps
```

Tous les conteneurs doivent être **healthy**.

4. Démarrer l'orchestrateur pour la rotation polymorphe :

```bash
python3 vault_orchestrator.py
```

---

## Services

### HAProxy

* Port exposé : `8080`
* Routage :

  * `/honeypot` → Honeypot
  * `/` → Paperless (cluster web1, web2, web3)

### Paperless

* Ports internes : `8000` (non exposés hors HAProxy)
* Volume partagé : `data` et `media`
* Accès via HAProxy : `http://localhost:8080/` ou via zrok pour l’exposer sur internet.
* Trois conteneurs pour haute disponibilité.
* Orchestrateur Python pour la rotation dynamique, assurant qu'un seul conteneur est actif à la fois mais tous restent disponibles.

### Honeypot

* Port interne : `5000` (non exposé hors HAProxy)
* Toutes les routes commencent par `/honeypot`.
* Dashboard sécurisé accessible après login.
* Favicon spécifique `/honeypot/static/favicon.png` sur tous les sous-chemins.

### Redis & Postgres

* Redis : `6379`
* Postgres : `5432`
* Utilisés uniquement par Paperless.

---

## Points importants

* **Volumes** : tous les Paperless utilisent le même volume pour `data` et `media`. Plus besoin de MinIO.
* **Healthchecks** : configurés pour tous les conteneurs afin d’assurer un démarrage stable de HAProxy même si un conteneur est temporairement éteint.
* **Reverse proxy** : HAProxy route correctement `/honeypot` et `/` sans dépendre de chemins spécifiques.
* **zrok** : le setup fonctionne derrière un tunnel zrok, avec les headers configurés pour Paperless.
* **Polymorphisme** : l'orchestrateur Python arrête et démarre les conteneurs Paperless aléatoirement toutes les X secondes, tout en maintenant la disponibilité du service.

---

## Commandes utiles

* Redémarrer un conteneur :

```bash
docker restart <container_name>
```

* Vérifier un healthcheck :

```bash
docker exec <container_name> curl -f http://localhost:<port>/honeypot/health
```

* Arrêter tous les conteneurs :

```bash
docker-compose down
```

* Voir les logs en temps réel :

```bash
docker-compose logs -f
```

---

## Notes

* Le projet est conçu pour être **robuste**, même si certains conteneurs Paperless sont arrêtés ou redémarrés.
* Le honeypot capture toutes les requêtes sur `/honeypot` et ses sous-chemins, avec un logging complet pour analyses futures.

