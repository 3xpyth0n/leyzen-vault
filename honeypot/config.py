# honeypot/config.py
import os, secrets, ipaddress

# App config via env (no secrets hard-coded)
HONEYPOT_USER = os.environ.get("HONEYPOT_USER", "admin")
HONEYPOT_PASSWORD = os.environ.get("HONEYPOT_PASSWORD", None)
HONEYPOT_TOKEN = os.environ.get("HONEYPOT_TOKEN", secrets.token_urlsafe(24))
HONEYPOT_SECRET = os.environ.get("HONEYPOT_SECRET", secrets.token_urlsafe(32))

# Log file
LOG_FILE = os.environ.get("HONEYPOT_LOG_FILE", "/app/honeypot_requests.jsonl")

# Networks to ignore (comma-separated CIDRs)
IGNORE_NETS_RAW = os.environ.get(
    "HONEYPOT_IGNORE_NETS",
    ""
)
IGNORE_NETS = []
for part in [p.strip() for p in IGNORE_NETS_RAW.split(",") if p.strip()]:
    try:
        IGNORE_NETS.append(ipaddress.ip_network(part))
    except Exception:
        pass
