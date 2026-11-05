"""
Serves the COS3 UI (ui/ folder) and the API that starts/stops NOS3.

Usage (in the Ubuntu terminal, with Docker Desktop running):
    python3 ui_server.py   then open http://localhost:3001

API (requires the `X-COS3: 1` header):
    GET  /api/status          current simulation state
    GET  /api/config/default  default NOS3 configuration (read from backend/cfg)
    POST /api/launch   start the container and NOS3: default configuration, or a custom one
                       with body {"values": {"startUtc", "durationS", "components"}}
    POST /api/stop     stop NOS3 and the container
"""

import json
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

import custom_config
from default_config import ConfigError, load_default_config
from launcher import launcher

ROOT_DIR = Path(__file__).resolve().parent
UI_DIR = ROOT_DIR / "ui"

HOST = "127.0.0.1"
PORT = 3001
ALLOWED_HOSTS = [f"localhost:{PORT}", f"127.0.0.1:{PORT}"]

MAX_BODY_BYTES = 64 * 1024


class Handler(SimpleHTTPRequestHandler):
    """Serves files from ui/ and the /api/* endpoints."""

    # Explicit types, so .js and .css are served correctly on every OS
    extensions_map = {
        **SimpleHTTPRequestHandler.extensions_map,
        ".html": "text/html",
        ".css": "text/css",
        ".js": "text/javascript",
    }

    def do_GET(self):
        if not self._allowed():
            return
        path = urlsplit(self.path).path

        if not path.startswith("/api/"):
            return super().do_GET()
        if not self._api_allowed():
            return

        if path == "/api/status":
            self._send_json(200, launcher.status())
        elif path == "/api/config/default":
            try:
                self._send_json(200, load_default_config())
            except ConfigError as err:
                self._send_json(500, {"error": str(err)})
        else:
            self._send_json(404, {"error": "Not found"})

    def do_HEAD(self):
        if self._allowed():
            super().do_HEAD()

    def do_POST(self):
        if not self._allowed() or not self._api_allowed():
            return
        path = urlsplit(self.path).path

        if path == "/api/launch":
            # Optional body {"values": {...}} for a custom configuration; no body = default
            try:
                values = self._read_json().get("values")
                values = custom_config.validate(values) if values is not None else None
            except ValueError as err:
                return self._send_json(400, {"error": str(err)})
            operation = ("starting", lambda: launcher.launch(values))
        elif path == "/api/stop":
            operation = ("stopping", launcher.stop)
        else:
            return self._send_json(404, {"error": "Not found"})

        if launcher.begin(*operation):
            self._send_json(202, {"state": launcher.state})
        else:
            self._send_json(409, {"error": "Busy"})

    def _read_json(self):
        """The request's JSON body as a dict ({} if there is none). Raises ValueError if invalid."""
        length = int(self.headers.get("Content-Length") or 0)
        if length == 0:
            return {}
        if length > MAX_BODY_BYTES:
            raise ValueError("Request too large.")
        try:
            body = json.loads(self.rfile.read(length))
        except json.JSONDecodeError:
            raise ValueError("Invalid JSON.") from None
        if not isinstance(body, dict):
            raise ValueError("Invalid JSON.")
        return body

    def _allowed(self):
        # Reject DNS rebinding and cross-site requests: the API runs local commands
        if self.headers.get("Host") not in ALLOWED_HOSTS:
            self.send_error(403, "Forbidden")
            return False
        return True

    def _api_allowed(self):
        # A custom header forces a CORS preflight, which this server never approves
        if self.headers.get("X-COS3") != "1":
            self._send_json(403, {"error": "Forbidden"})
            return False
        return True

    def _send_json(self, status, body):
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def list_directory(self, path):
        # Don't show folder listings (e.g. /assets/)
        self.send_error(404, "Not found")
        return None

    def log_message(self, format, *args):
        # The page polls /api/status every few seconds; keep the terminal quiet
        pass


def main():
    handler = partial(Handler, directory=str(UI_DIR))
    server = ThreadingHTTPServer((HOST, PORT), handler)
    print(f"COS3 UI running at http://localhost:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
