# Leyzen Vault PoC

## Description

Ce projet est une **preuve de concept pour Leyzen Vault**, un environnement local de documentation et de honeypot simulé, avec une architecture multi-conteneurs Docker orchestrée via docker-compose et un orchestrateur Python pour la rotation polymorphe des services Paperless.

Il inclut :

- **Paperless-ngx** : système de gestion documentaire, déployé sur 3 conteneurs avec rotation dynamique.
- **Honeypot custom** : pour simuler des attaques et collecter des logs (IP, User-Agent, chemins).
- **HAProxy** : pour router le trafic HTTP vers Paperless ou le honeypot.
- **Redis et Postgres** : backends de Paperless.
- **Volumes partagés** : data et media communs aux conteneurs Paperless.
- **Vault Orchestrator** : script Python qui orchestre la rotation polymorphe des conteneurs Paperless et expose un tableau de bord en temps réel (statuts, uptimes, logs).

## Architecture

```
                   ┌─────────────────────┐
                   │       Client        │
                   └──────────┬──────────┘
                              │
                              ▼
                      ┌───────────────┐
                      │  HAProxy 8080 │
                      └───────┬───────┘
              ┌───────────────┴───────────────┐
              │                               │
              ▼                               ▼
     ┌─────────────────┐             ┌───────────────────┐
     │ Honeypot Flask  │             │   Paperless-ngx   │
     │   /honeypot/*   │             │   cluster web1-3  │
     │  (port interne) │             │   (rotation dyn.) │
     └─────────────────┘             └───────────────────┘


         ┌────────────────────────────────────────┐
         │ Vault Orchestrator Dashboard (Flask)   │
         │ Port : 8081                            │
         │                                        │
         │ • `/` → UI (statuts + graphiques)      │
         │ • `/api/status` → API JSON             │
         │ • `/logs` → lecture de vault_orchestr. │
         └────────────────────────────────────────┘
```

## Prérequis

- Docker
- Docker Compose
- Git
- Python 3.x

## Installation et lancement

1.  Cloner le repo :

```bash
git clone git@github.com:3xpyth0n/leyzen-vault.git
cd leyzen-vault
```

1.  Construire et démarrer les conteneurs :

```bash
docker-compose up --build -d
```

1.  Vérifier l’état des conteneurs :

```bash
docker ps
```

Tous les conteneurs doivent être **healthy**.

1.  Lancer l’orchestrateur pour la rotation polymorphe et le dashboard :

```bash
python3 orchestrator/vault_orchestrator.py
```

## Services

### HAProxy

- Port exposé : 8080
- Routage :
  - /honeypot/\* → Honeypot
  - / → Paperless cluster

### Paperless

- Ports internes : 8000 (non exposés directement)
- Volumes partagés : data et media
- Accès via : http://localhost:8080/
- Rotation orchestrée par le Vault Orchestrator → un seul conteneur actif à la fois, mais service toujours disponible.

### Honeypot

- Port interne : 5000 (non exposé hors HAProxy)
- Routes accessibles via /honeypot/\*
- Capture des requêtes (IP, User-Agent, chemin, date).
- Faux endpoints inclus (/admin, /server-status, etc.).

### Vault Orchestrator Dashboard

- Port exposé : 8081
- Accessible directement (pas via HAProxy).
- Routes :
  - / → Dashboard (statuts conteneurs, rotations, graphique en temps réel).
  - /logs → consultation du fichier vault_orchestrator.log.

### Redis & Postgres

- Redis : 6379
- Postgres : 5432
- Exclusivement utilisés par Paperless.

## Points importants

- **Volumes** : les 3 Paperless partagent le même volume → persistance commune.
- **Healthchecks** : utilisés pour la stabilité et la supervision.
- **Orchestrateur Python** : arrête/démarre les conteneurs aléatoirement toutes les X secondes.
- **Polymorphisme** : un attaquant ne peut pas persister, car le service ciblé sera inévitablement stoppé.
- **Dashboard 8081** : permet le suivi temps réel (uptime, statuts, logs).

## Notes

- L’environnement est conçu pour rester disponible même si des conteneurs sont arrêtés/restart.
- Le honeypot capture toutes les tentatives sur /honeypot/\* et fournit un tableau de suivi.
- Le tableau de bord Flask (port 8081) centralise la visibilité sur les rotations et journaux.
