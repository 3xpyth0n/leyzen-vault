# Leyzen Vault

## Description

**Leyzen Vault** est une preuve de concept démontrant un environnement de service dynamique.
Le projet repose sur un orchestrateur écrit en Python, chargé de gérer la rotation automatique et aléatoires de plusieurs instances Paperless, utilisées ici comme exemple de service applicatif dont le back-end change continuellement.
Cette rotation illustre le principe d’une infrastructure mouvante, où les composants ne restent jamais statiques afin de renforcer la sécurité.

Il inclut :

- **Paperless-ngx** : gestion documentaire sur trois conteneurs avec rotation polymorphe.
- **Vault Orchestrator** : conteneur Python orchestrant la rotation des conteneurs et fournissant un tableau de bord en temps réel (statuts, uptimes, logs).
- **HAProxy** : routage HTTP vers Paperless ou l'orchestrateur.
- **Redis et Postgres** : backends nécessaires à Paperless.
- **Volumes partagés** : volumes docker communs aux conteneurs Paperless.

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
  │  Orchestrateur  │             │   Paperless-ngx   │
  │  /orchestrator  │             │    cluster web    │
  │   (dashboard)   │             │  (rotation dyn.)  │
  └─────────────────┘             └───────────────────┘
```

## Prérequis

- Docker
- Git

## Installation et lancement

L’installation et le lancement du projet se font en **3 commandes simples** :

```bash
git clone git@github.com:3xpyth0n/leyzen-vault.git
cd leyzen-vault
sudo ./install.sh
```

Une fois le service actif, vérifier son état via :

```bash
sudo systemctl status leyzen.service
```

Et consulter les logs :

```bash
journalctl -u leyzen.service -f
```

## Services

### HAProxy

- **Port exposé** : 8080
- **Routage** :
  - `/` → Paperless cluster
  - `/orchestrator` → Vault Orchestrator dashboard

### Paperless

- **Accès via** : [http://localhost:8080/](http://localhost:8080/)
- **Volumes partagés** : data et media → persistance des données utilisateurs
- **Rotation** : orchestrée par Vault Orchestrator, un conteneur actif à la fois, service toujours disponible.

### Vault Orchestrator Dashboard

- Accessible via HAProxy sur [http://localhost:8080/orchestrator](http://localhost:8080/orchestrator)
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

- **Confinement** : Tout est confiné à l’intérieur de Docker, dans un réseau bridge isolé, seul le HAProxy est exposé.
- **Healthchecks** garantissant stabilité et supervision.
- **Orchestrateur Python** : arrête et démarre les conteneurs aléatoirement pour une rotation polymorphe.
- **Polymorphisme** : empêche la persistance d’attaques sur un conteneur spécifique.
- **Volumes partagés** assurant la persistance des données Paperless.

## Notes

- L’environnement reste fonctionnel même si certains conteneurs sont arrêtés ou redémarrés.
- Le tableau de bord `/orchestrator` fournit un suivi centralisé de toutes les rotations et journaux.

## Copyright

**_Auteur_** _: Saad Idrissi_
