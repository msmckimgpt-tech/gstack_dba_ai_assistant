#!/usr/bin/env python3
"""TASK-0130 (#4/#5): web Docker HEALTHCHECK — GET /healthz.

web 은 override 적용 시 자체 TLS(HTTPS), 미적용 시 HTTP 로 8000 을 서빙하므로 https→http
순으로 시도한다. /healthz 가 200(ok) 이면 healthy, 503(degraded: mysql/pg down) 또는
미응답이면 unhealthy.
"""
import ssl
import sys
import urllib.request

PORT = 8000
PATHS = (f"https://localhost:{PORT}/healthz", f"http://localhost:{PORT}/healthz")
_ctx = ssl.create_default_context()
_ctx.check_hostname = False
_ctx.verify_mode = ssl.CERT_NONE

for url in PATHS:
    try:
        if url.startswith("https"):
            resp = urllib.request.urlopen(url, timeout=5, context=_ctx)
        else:
            resp = urllib.request.urlopen(url, timeout=5)
        sys.exit(0 if getattr(resp, "status", 0) == 200 else 1)
    except Exception:
        continue
sys.exit(1)
