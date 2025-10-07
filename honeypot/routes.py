# honeypot/routes.py
from flask import Blueprint, request, jsonify, render_template, render_template_string, redirect, url_for, session, make_response
from werkzeug.security import generate_password_hash, check_password_hash
import config, utils, json, random, os

bp = Blueprint("honeypot", __name__, url_prefix="/honeypot", template_folder="templates", static_folder="static")

# prepare hashed password in runtime (not stored in code)
if config.HONEYPOT_PASSWORD:
    HONEYPOT_PASS_HASH = generate_password_hash(config.HONEYPOT_PASSWORD)
else:
    rand_pw = os.environ.get("HONEYPOT_TEMP_PW", None)
    if not rand_pw:
        rand_pw = "temporary"  # fallback (should not happen)
    HONEYPOT_PASS_HASH = generate_password_hash(rand_pw)

def check_session():
    return session.get("logged_in") is True and session.get("user") == config.HONEYPOT_USER

def require_token_or_session(func):
    def wrapper(*a, **kw):
        token = request.headers.get("X-Leyzen-Token")
        if token and token == config.HONEYPOT_TOKEN:
            return func(*a, **kw)
        if check_session():
            return func(*a, **kw)
        return ("Unauthorized", 401)
    wrapper.__name__ = func.__name__
    return wrapper

@bp.route("/")
def index():
    return redirect(url_for("honeypot.dashboard"))

@bp.route("/favicon.ico")
def favicon():
    return redirect(url_for("honeypot.static", filename="favicon.png"))

@bp.route("/health")
def health():
    return "OK", 200

# Decoy login pages (GET)
@bp.route("/admin", methods=["GET"])
@bp.route("/admin/login", methods=["GET"])
@bp.route("/wp-login.php", methods=["GET"])
@bp.route("/login.php", methods=["GET"])
def decoy_login_pages():
    utils.maybe_delay()
    path = request.path.lower()
    if "wp-login" in path:
        html = '''<html><head><title>Log In ‹ WordPress — wp-login</title></head><body>
            <h1>WordPress</h1>
            <form method="post" action="/honeypot/wp-login.php"><input name="log"><input name="pwd" type="password"><button>Log In</button></form>
            </body></html>'''
        resp = make_response(render_template_string(html))
        resp.headers["Server"] = "Apache/2.4.46 (Ubuntu)"
        utils.record_request(request, note="decoy_wp_login")
        return resp
    html = '''<html><head><title>Admin Login</title></head><body>
        <h1>Administration</h1>
        <form method="post" action="/honeypot/admin/login"><input name="username"><input name="password" type="password"><button>Connexion</button></form>
        </body></html>'''
    resp = make_response(render_template_string(html))
    resp.headers["Server"] = "nginx/1.18.0"
    utils.record_request(request, note="decoy_admin_login")
    return resp

# Decoy login POSTs
@bp.route("/admin/login", methods=["POST"])
@bp.route("/wp-login.php", methods=["POST"])
def decoy_login_submit():
    utils.maybe_delay()
    utils.record_request(request, note="decoy_login_submit")
    html = "<html><body><h1>Login failed</h1><p>Wrong credentials.</p></body></html>"
    resp = make_response(render_template_string(html), 200)
    resp.headers["Server"] = random.choice(["Apache/2.4.46 (Ubuntu)", "nginx/1.18.0"])
    return resp

@bp.route("/robots.txt")
def robots():
    utils.maybe_delay()
    txt = "User-agent: *\nDisallow: /admin/\nDisallow: /wp-admin/\n"
    utils.record_request(request, note="robots")
    return make_response(txt, 200, {"Content-Type":"text/plain","Server":"nginx/1.19.6"})

@bp.route("/server-status")
def server_status():
    utils.maybe_delay()
    utils.record_request(request, note="server_status")
    html = "<html><body><h1>Apache Server Status</h1><pre>Server uptime: 231635</pre></body></html>"
    resp = make_response(render_template_string(html), 200)
    resp.headers["Server"] = "Apache/2.4.29 (Ubuntu)"
    return resp

@bp.route("/api/v1/status")
def api_status():
    utils.maybe_delay()
    utils.record_request(request, note="api_status")
    data = {"status":"ok","version":"2.6.12","uptime":87654652932}
    resp = jsonify(data)
    resp.headers["Server"] = "gunicorn/20.1.0"
    return resp

# Generic catchall - excludes legitimate UI GETs handled elsewhere
@bp.route("/<path:path>", methods=["GET","POST","PUT","DELETE","PATCH","OPTIONS","HEAD"])
def honeypot_catchall(path):
    lower = path.lower()
    if lower.startswith("dashboard") or lower.startswith("login"):
        return ("Not Found", 404)
    if lower == "health":
        return ("OK", 200)
    utils.maybe_delay()
    if lower.endswith(".env") or lower.endswith("config.php") or lower.endswith("composer.json"):
        utils.record_request(request, note="probe_sensitive_file")
        return ("Forbidden", 403)
    utils.record_request(request, note="decoy_generic")
    html = f"<html><head><title>{path}</title></head><body><h1>Page: /{path}</h1><p>Nothing much here.</p></body></html>"
    resp = make_response(render_template_string(html), 200)
    resp.headers["Server"] = random.choice(["nginx/1.21.0","Apache/2.4.41 (Ubuntu)","lighttpd/1.4.53"])
    return resp

# Logs, download endpoints (use require_token_or_session)
@bp.route("/logs")
@require_token_or_session
def get_logs():
    limit = int(request.args.get("limit", 20))
    page = int(request.args.get("page", 1))
    method = request.args.get("method", "")
    path_filter = request.args.get("path", "")

    logs = []
    try:
        with open(config.LOG_FILE, "r") as f:
            all_logs = [json.loads(line) for line in f]

            # filtrage
            if method:
                all_logs = [l for l in all_logs if l.get("method") == method]
            if path_filter:
                all_logs = [l for l in all_logs if path_filter in l.get("path", "")]

            total = len(all_logs)
            page_count = (total + limit - 1) // limit  # arrondi sup

            start = (page - 1) * limit
            end = start + limit
            logs = all_logs[start:end]

            return jsonify({
                "logs": logs,
                "total": total,
                "page_count": page_count,
                "page": page
            })
    except FileNotFoundError:
        return jsonify({"logs": [], "total": 0, "page_count": 0, "page": page})

@bp.route("/download/json")
@require_token_or_session
def download_json():
    try:
        with open(config.LOG_FILE, "r", encoding="utf-8") as f:
            logs = [json.loads(l) for l in f]
    except Exception:
        logs = []
    resp = make_response(json.dumps(logs, ensure_ascii=False, indent=2))
    resp.headers["Content-Disposition"] = "attachment; filename=honeypot_logs.json"
    resp.headers["Content-Type"] = "application/json; charset=utf-8"
    return resp

@bp.route("/download/csv")
@require_token_or_session
def download_csv():
    try:
        with open(config.LOG_FILE, "r", encoding="utf-8") as f:
            logs = [json.loads(l) for l in f]
    except Exception:
        logs = []
    output = []
    header = ["timestamp","method","path","remote_addr","body","args","note"]
    output.append(",".join(header))
    for log in logs:
        row = [
            log.get("timestamp",""),
            log.get("method",""),
            log.get("path",""),
            log.get("remote_addr",""),
            '"' + str(log.get("body","")).replace('"','""') + '"',
            '"' + json.dumps(log.get("args",{}), ensure_ascii=False).replace('"','""') + '"',
            '"' + str(log.get("note","")).replace('"','""') + '"'
        ]
        output.append(",".join(row))
    resp = make_response("\n".join(output))
    resp.headers["Content-Disposition"] = "attachment; filename=honeypot_logs.csv"
    resp.headers["Content-Type"] = "text/csv; charset=utf-8"
    return resp

# Login/logout/dashboard (UI)
@bp.route("/login", methods=["GET","POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")
    username = request.form.get("username","")
    password = request.form.get("password","")
    if utils.verify_user_plain(username, password, HONEYPOT_PASS_HASH):
        session.clear()
        session["logged_in"] = True
        session["user"] = username
        return redirect(url_for("honeypot.dashboard"))
    utils.record_request(request, note="failed_login", force=True)
    return render_template("login.html", error="Identifiants incorrects"), 401

@bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("honeypot.login"))

@bp.route("/dashboard")
def dashboard():
    if not check_session():
        return redirect(url_for("honeypot.login"))
    try:
        with open(config.LOG_FILE, "r", encoding="utf-8") as f:
            lines = [l for l in f.read().splitlines() if "/honeypot/health" not in l]
    except Exception:
        lines = []
    logs = []
    for line in lines[-200:]:
        try:
            logs.append(json.loads(line))
        except Exception:
            continue
    return render_template("dashboard.html", logs=list(reversed(logs)), user=config.HONEYPOT_USER)
