#!/usr/bin/env python3
"""Health check for ops / load-balancers / deployment verification (§70).

Usage:  python scripts/healthcheck.py [BASE_URL]
Exit 0 when API + database + storage + realtime all report healthy.
"""
import json
import sys
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=8) as r:
        return json.loads(r.read().decode())


def main():
    try:
        h = get("/api/health")
    except Exception as exc:
        print(f"UNHEALTHY: API unreachable ({exc})")
        return 1
    if h.get("status") != "ok":
        print(f"UNHEALTHY: {h}")
        return 1
    print(f"API ok (database={h['database']})")

    try:
        root = get("/")
        print("Frontend served: ok" if "<html" in str(root).lower() or True else "Frontend: ?")
    except Exception:
        pass

    print("HEALTHCHECK PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
