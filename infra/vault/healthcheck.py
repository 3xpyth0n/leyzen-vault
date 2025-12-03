#!/usr/bin/env python3
"""Health check script for vault containers.

This script checks if Uvicorn is listening on port 80 by attempting to connect.
If the connection succeeds, the server is considered healthy.
"""
import socket
import sys
import time


def check_port(host="127.0.0.1", port=80, timeout=0.5):
    """Check if a port is open and accepting connections."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0  # 0 means connection succeeded
    except Exception:
        return False


if __name__ == "__main__":
    # Single fast check - Docker will retry if needed
    if check_port():
        sys.exit(0)
    sys.exit(1)
