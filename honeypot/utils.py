# honeypot/utils.py
import json, time, random, ipaddress, os
from datetime import datetime
from flask import session
import config

def now_iso():
    return datetime.utcnow().isoformat() + "Z"

def ensure_logfile():
    logpath = config.LOG_FILE
    d = os.path.dirname(logpath)
    if d and not os.path.exists(d):
        try:
            os.makedirs(d, exist_ok=True)
        except Exception as e:
            print("[HONEYPOT][ERROR] could not create log dir:", e)
    try:
        if not os.path.exists(logpath):
            open(logpath, "a", encoding="utf-8").close()
        try:
            os.chmod(logpath, 0o666)
        except Exception:
            pass
    except Exception as e:
        print("[HONEYPOT][ERROR] could not ensure logfile:", e)

def get_client_ip(req):
    # prefer X-Forwarded-For if present (comma-separated), else remote_addr
    xff = req.headers.get("X-Forwarded-For")
    if xff:
        return xff.split(",")[0].strip()
    return req.remote_addr

def record_request(req, note=None, force=False, always_create=True):
    """
    Write JSON line in config.LOG_FILE. No IP filtering (POC mode).
    """
    if always_create:
        ensure_logfile()

    remote = get_client_ip(req) or ""

    entry = {
        "timestamp": now_iso(),
        "method": req.method,
        "path": req.path,
        "remote_addr": remote,
        "headers": dict(req.headers),
        "args": req.args.to_dict(),
        "body": req.get_data(as_text=True),
        "note": note or ""
    }
    try:
        with open(config.LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        print("[HONEYPOT][ERROR] write log:", e)
    print("[HONEYPOT] " + json.dumps(entry, ensure_ascii=False))
    return entry

def maybe_delay():
    time.sleep(random.uniform(0.05, 0.4))

def verify_user_plain(username, password, hashed_password):
    from werkzeug.security import check_password_hash
    return username and password and check_password_hash(hashed_password, password)

