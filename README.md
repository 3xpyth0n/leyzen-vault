# Leyzen Vault PoC

## Description

**Leyzen Vault PoC** est une preuve de concept offrant un environnement local de documentation et de honeypot simulé, orchestré via Docker et un script Python pour la rotation dynamique des services Paperless.

Il inclut :

- **Paperless-ngx** : gestion documentaire sur trois conteneurs avec rotation polymorphe.
- **HAProxy** : routage HTTP vers Paperless ou l'orchestrateur.
- **Redis et Postgres** : backends nécessaires à Paperless.
- **Volumes partagés** : data et media communs aux conteneurs Paperless.
- **Vault Orchestrator** : script Python orchestrant la rotation des conteneurs et fournissant un tableau de bord en temps réel (statuts, uptimes, logs).

## Architecture

```
                   ┌───────────────┐
                   │    Client     │
                   └───────┬───────┘
                           │
                           ▼
                   ┌───────────────┐
                   │  HAProxy 8080 │
                   └───────┬───────┘
           ┌───────────────┴───────────────┐
           │                               │
           ▼                               ▼
  ┌─────────────────┐             ┌───────────────────┐
  │  Orchestrator   │             │   Paperless-ngx   │
  │  /orchestrator  │             │  cluster web1-3   │
  │  (dashboard)    │             │  (rotation dyn.)  │
  └─────────────────┘             └───────────────────┘
```

## Prérequis

- Docker
- Git
- Python 3.x

## Installation et lancement

1. Cloner le dépôt :

```bash
git clone git@github.com:3xpyth0n/leyzen-vault.git
cd leyzen-vault
```

2. Construire et démarrer les conteneurs :

```bash
docker compose up --build -d
```

3. Vérifier l’état des conteneurs :

```bash
docker ps
```

Tous les conteneurs doivent être **healthy**.

4. Lancer l’orchestrateur pour activer la rotation polymorphe et le dashboard :

```bash
python3 orchestrator/vault_orchestrator.py
```

## Services

### HAProxy

- **Port exposé** : 8080
- **Routage** :
  - `/` → Paperless cluster
  - `/orchestrator` → Vault Orchestrator dashboard

### Paperless

- **Accès via** : [http://localhost:8080/](http://localhost:8080/)
- **Volumes partagés** : data et media
- **Rotation** : orchestrée par Vault Orchestrator, un conteneur actif à la fois, service toujours disponible.

### Vault Orchestrator Dashboard

- Accessible via HAProxy sur `/orchestrator`
- **Fonctionnalités** :
  - Statuts des conteneurs
  - Rotation en temps réel
  - Graphiques d'uptime
  - Accès aux logs

### Redis & Postgres

- Redis : 6379
- Postgres : 5432
- Exclusivement utilisés par Paperless

## Points importants

- **Volumes partagés** assurant la persistance des données Paperless.
- **Healthchecks** garantissant stabilité et supervision.
- **Orchestrateur Python** : arrête et démarre les conteneurs aléatoirement pour simuler une rotation polymorphe.
- **Polymorphisme** : empêche la persistance d’attaques sur un conteneur spécifique.
- **Dashboard** : visibilité centralisée sur rotations, uptimes et logs.

## Notes

- L’environnement reste fonctionnel même si certains conteneurs sont arrêtés ou redémarrés.
- Le tableau de bord `/orchestrator` fournit un suivi centralisé de toutes les rotations et journaux.
