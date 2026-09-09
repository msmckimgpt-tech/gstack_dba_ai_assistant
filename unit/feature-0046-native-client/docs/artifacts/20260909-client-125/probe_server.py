"""격리 검증용 기록 서버 — 앱이 **어느 경로로** 갔는지만 적는다. 서비스에 닿지 않는다."""
import http.server, sys, datetime, threading
LOG = sys.argv[2]
class H(http.server.BaseHTTPRequestHandler):
    def _log(self):
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(f"{datetime.datetime.now().isoformat(timespec='seconds')} {self.command} {self.path}\n")
    def do_GET(self):
        self._log()
        body = b"<!doctype html><meta charset=utf-8><title>probe</title><h1>probe</h1>"
        self.send_response(200); self.send_header("Content-Type","text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
    def do_POST(self): self.do_GET()
    def log_message(self, *a): pass
http.server.ThreadingHTTPServer(("127.0.0.1", int(sys.argv[1])), H).serve_forever()
