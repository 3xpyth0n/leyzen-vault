#!/usr/bin/env python3
"""Health check script for vault containers.

This script checks if the /healthz endpoint responds correctly with {"status":"ok"}.
If the endpoint responds with 200 and the correct JSON, the server is considered healthy.
Any other response (timeout, 503, wrong JSON, etc.) means the server is unhealthy.
"""
import json
import sys
import urllib.request
import urllib.error


def check_healthz(host="127.0.0.1", port=80, timeout=1.0):
    """Check if /healthz endpoint responds correctly.

    Args:
        host: Host to check (default: 127.0.0.1)
        port: Port to check (default: 80)
        timeout: Timeout in seconds (default: 1.0)

    Returns:
        True if healthz returns 200 with {"status":"ok"}, False otherwise
    """
    try:
        url = f"http://{host}:{port}/healthz"
        req = urllib.request.Request(url)
        req.add_header("User-Agent", "Docker-Healthcheck/1.0")

        with urllib.request.urlopen(req, timeout=timeout) as response:
            # Check status code
            if response.getcode() != 200:
                return False

            # Check content type
            content_type = response.headers.get("Content-Type", "")
            if "application/json" not in content_type:
                return False

            # Read and parse JSON response
            body = response.read().decode("utf-8")
            try:
                data = json.loads(body)
                # Must have status: "ok"
                return data.get("status") == "ok"
            except (json.JSONDecodeError, KeyError):
                return False

    except urllib.error.URLError:
        # Timeout or connection error
        return False
    except Exception:
        # Any other error
        return False


if __name__ == "__main__":
    # Single fast check - Docker will retry if needed
    if check_healthz():
        sys.exit(0)
    sys.exit(1)
