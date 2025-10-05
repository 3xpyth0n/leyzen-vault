#!/usr/bin/env python3
from flask import Flask
import config

app = Flask(
    __name__,
    static_url_path="/honeypot/static",
    static_folder="static",
    template_folder="templates"
)
app.secret_key = config.HONEYPOT_SECRET

# Register blueprint
from routes import bp as honeypot_bp
app.register_blueprint(honeypot_bp)

# Trust reverse proxy headers (safety) — still useful if X-Forwarded-* used
from werkzeug.middleware.proxy_fix import ProxyFix
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)

if __name__ == "__main__":
    print("[HONEYPOT] launching app (modular) - user:", config.HONEYPOT_USER)
    app.run(host="0.0.0.0", port=5000)

