#!/usr/bin/env python3
import docker
import time
import random
from datetime import datetime
import traceback

LOG_FILE = "./vault_orchestrator.log"

client = docker.from_env()
web_containers = ["lyz_nginx", "lyz_apache", "lyz_lighttpd"]
interval = 30  # secondes entre chaque rotation

def log(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

def rotate():
    # Initialisation : arrêter tous les containers sauf un aléatoire
    new_active = random.choice(web_containers)
    for c in web_containers:
        cont = client.containers.get(c)
        cont.reload()
        if c == new_active:
            if cont.status != "running":
                log(f"Démarrage initial de {c}")
                cont.start()
        else:
            if cont.status == "running":
                log(f"Arrêt initial de {c}")
                cont.stop()
    log(f"Rotation initiale: {new_active} activé")

    active_container = new_active

    # Boucle principale
    while True:
        try:
            choices = [c for c in web_containers if c != active_container]
            new_active = random.choice(choices)

            # Stopper l'ancien container
            old_container = client.containers.get(active_container)
            old_container.reload()
            if old_container.status == "running":
                log(f"Arrêt de {active_container}")
                old_container.stop()

            # Démarrer le nouveau container
            new_container = client.containers.get(new_active)
            new_container.reload()
            if new_container.status != "running":
                log(f"Démarrage de {new_active}")
                new_container.start()

            # Log des statuts
            statuses = {c: client.containers.get(c).reload() or client.containers.get(c).status for c in web_containers}
            log(f"Rotation: {new_active} activé. Statuts: {statuses}")

            active_container = new_active
            time.sleep(interval)

        except Exception as e:
            log(f"Exception dans la boucle principale: {traceback.format_exc()}")
            time.sleep(5)

if __name__ == "__main__":
    log("=== Orchestrator démarré ===")
    try:
        rotate()
    except KeyboardInterrupt:
        log("Orchestrator arrêté par l'utilisateur (CTRL+C)")
        print("\n[INFO] Orchestrator arrêté proprement.")
