from flask import Flask, request
app = Flask(__name__)

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def catch_all(path):
    print(f"HONEYPOT - {request.method} {request.path}")
    return f"honeypot: logged {path}", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

