"""
Serves the COS3 UI (ui/ folder) and the API that starts/stops NOS3.

Usage (in the Ubuntu terminal, with Docker Desktop running):
    python3 ui_server.py   then open http://localhost:3001

API (requires the `X-COS3: 1` header):
    GET  /api/status          current simulation state
    GET  /api/session         {"loggedIn"}: whether the server has a COSMOS session
    GET  /api/config/default  default NOS3 configuration (read from backend/cfg)
    GET  /api/components      components enabled in the current simulation
    GET  /api/components/{key}/commands?path=DEBUG|RADIO
                              commands for an enabled component (needs a COSMOS login)
    GET  /api/commands/{target}/{name}
                              one command and its settable parameters (needs a COSMOS login)
    POST /api/commands/{target}/{name}/validate
                              body {"values": {name: value}} -> {"errors": {name: message}}
                              (commands/validation.py is the only place parameters are checked)
    POST /api/commands/{target}/{name}
                              send: body {"values", "confirmHazardous"} -> {"record"} (its "status" is
                              sent | rejected | failed), 400 {"errors"}, or 409 {"confirm": reason}
    GET  /api/history         {"commands": [record, ...]}, newest first
    POST /api/history/{id}/resend
                              body {"confirmHazardous"}: send a recorded command again (same answers as send)
    POST /api/launch   start the container and NOS3: default configuration, or a custom one
                       with body {"values": {"startUtc", "durationS", "components"}}
    POST /api/stop     stop NOS3 and the container
    POST /api/login    body {"password"}: log in to COSMOS
    POST /api/noop     body {"path": "DEBUG" | "RADIO"}: send GENERIC_MAG_NOOP_CC
"""

import json
import re
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import custom_config
from cosmos_client import CosmosError, CosmosJSONAPIClient, CosmosRejected, CosmosUnavailable, NotAuthenticated
from current_config import load_enabled_components
from default_config import ConfigError, load_default_config
from launcher import launcher
from commands.targets import CommandPath, UnknownComponent, component_for
from commands.command_catalog import CommandCatalog, UnknownCommand
from commands.history import CommandHistory, UnknownRecord
from commands.sender import CommandSender, ConfirmationRequired, ValidationFailed
from commands.validation import validate

ROOT_DIR = Path(__file__).resolve().parent
UI_DIR = ROOT_DIR / "ui"

HOST = "127.0.0.1"
PORT = 3000
ALLOWED_HOSTS = [f"localhost:{PORT}", f"127.0.0.1:{PORT}"]

MAX_BODY_BYTES = 64 * 1024

cosmos = CosmosJSONAPIClient()
catalog = CommandCatalog(cosmos)
history = CommandHistory()
sender = CommandSender(cosmos, catalog, history)

# Routes with path parameters
COMPONENT_COMMANDS = re.compile(r"^/api/components/(?P<key>[a-z0-9_]+)/commands$")
COMMAND = re.compile(r"^/api/commands/(?P<target>[A-Z0-9_]+)/(?P<name>[A-Z0-9_]+)$")
COMMAND_VALIDATE = re.compile(r"^/api/commands/(?P<target>[A-Z0-9_]+)/(?P<name>[A-Z0-9_]+)/validate$")
RESEND = re.compile(r"^/api/history/(?P<id>\d+)/resend$")


def enabled_component_keys():
    """Keys of the components enabled in the current simulation. Raises ConfigError."""
    return {c["key"] for c in load_enabled_components()["spacecraft"]["components"]}


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
        elif path == "/api/history":
            self._send_json(200, {"commands": [r.to_dict() for r in history.list()]})
        elif path == "/api/session":
            self._send_json(200, {"loggedIn": cosmos.authenticated})
        elif path == "/api/config/default":
            try:
                self._send_json(200, load_default_config())
            except ConfigError as err:
                self._send_json(500, {"error": str(err)})
        elif path == "/api/components":
            try:
                self._send_json(200, load_enabled_components())
            except ConfigError as err:
                self._send_json(500, {"error": str(err)})
        elif match := COMPONENT_COMMANDS.match(path):
            query = parse_qs(urlsplit(self.path).query)
            self._component_commands(match["key"], query.get("path", ["DEBUG"])[0])
        elif match := COMMAND.match(path):
            self._command(match["target"], match["name"])
        else:
            self._send_json(404, {"error": "Not found"})

    def _command(self, target, name):
        """GET /api/commands/{target}/{name}: one command and its parameters, if its component is enabled."""
        definition = self._find_command(target, name)
        if definition is not None:
            self._send_json(200, definition.to_dict())

    def _validate_command(self, target, name):
        """POST /api/commands/{target}/{name}/validate: check parameter values without sending.

        Always 200 when the command exists: {"errors": {}} means every value is valid.
        """
        try:
            values = self._read_json().get("values", {})
        except ValueError as err:
            return self._send_json(400, {"error": str(err)})
        if not isinstance(values, dict):
            return self._send_json(400, {"error": "values must be an object."})

        definition = self._find_command(target, name)
        if definition is None:
            return
        _, errors = validate(definition, values)
        self._send_json(200, {"errors": errors})

    def _send_command(self, target, name):
        """POST /api/commands/{target}/{name}: validate, confirm hazards, send, record."""
        try:
            body = self._read_json()
        except ValueError as err:
            return self._send_json(400, {"error": str(err)})
        values = body.get("values", {})
        if not isinstance(values, dict):
            return self._send_json(400, {"error": "values must be an object."})
        if self._find_command(target, name) is None:  # also checks the component is enabled
            return
        self._run_send(lambda confirm: sender.send(target, name, values, confirm), body)

    def _resend(self, record_id):
        """POST /api/history/{id}/resend: send a recorded command again, if its component is still enabled."""
        try:
            body = self._read_json()
            previous = history.get(record_id)
        except ValueError as err:
            return self._send_json(400, {"error": str(err)})
        except UnknownRecord:
            return self._send_json(404, {"error": f"No command #{record_id} in the history."})
        key = component_for(previous.target)
        if key is None:
            return self._send_json(404, {"error": f"Unknown target {previous.target}."})
        if not self._component_enabled(key):
            return
        self._run_send(lambda confirm: sender.resend(record_id, confirm), body)

    def _run_send(self, send, body):
        """Run a send or resend and map its outcome to a response."""
        try:
            record = send(body.get("confirmHazardous") is True)
        except ValidationFailed as err:
            return self._send_json(400, {"error": str(err), "errors": err.errors})
        except ConfirmationRequired as err:
            return self._send_json(409, {"confirm": err.reason})
        except UnknownCommand as err:
            return self._send_json(404, {"error": f"Unknown command {err}."})
        except CosmosError as err:
            return self._send_cosmos_error(err)
        self._send_json(200, {"record": record.to_dict()})

    def _find_command(self, target, name):
        """The command's definition if its component is enabled; otherwise sends an error and returns None."""
        key = component_for(target)
        if key is None:
            self._send_json(404, {"error": f"Unknown target {target}."})
            return None
        if not self._component_enabled(key):
            return None
        try:
            return catalog.get_command(target, name)
        except UnknownCommand:
            self._send_json(404, {"error": f"Unknown command {target} {name}."})
        except CosmosError as err:
            self._send_cosmos_error(err)
        return None

    def _component_commands(self, key, path):
        """GET /api/components/{key}/commands: the component's commands, if it's enabled."""

        try:
            path = CommandPath(path)
        except ValueError:
            return self._send_json(400, {"error": "path must be DEBUG or RADIO"})

        if not self._component_enabled(key):
            return

        try:
            commands = catalog.list_commands(key, path)
        except UnknownComponent:
            return self._send_json(404, {"error": f"No COSMOS commands for component {key}."})
        except CosmosError as err:
            return self._send_cosmos_error(err)

        self._send_json(200, {"component": key, "path": path.value, "commands": [c.__dict__ for c in commands]})

    def _component_enabled(self, key):
        """Send 404 (or 500) and return False unless the component is enabled in the current simulation."""

        try:
            enabled = key in enabled_component_keys()
        except ConfigError as err:
            self._send_json(500, {"error": str(err)})
            return False

        if not enabled:
            self._send_json(404, {"error": f"Component {key} isn't enabled in this simulation."})

        return enabled

    def _send_cosmos_error(self, err):
        """Map a COSMOS client error to an HTTP status."""
        if isinstance(err, NotAuthenticated):
            status, message = 401, "Log in to COSMOS first."
        elif isinstance(err, CosmosUnavailable):
            status, message = 502, str(err)
        elif isinstance(err, CosmosRejected):
            status, message = 400, str(err)
        else:
            status, message = 502, str(err) or "COSMOS request failed."
        self._send_json(status, {"error": message})

    def do_HEAD(self):
        if self._allowed():
            super().do_HEAD()

    def do_POST(self):
        if not self._allowed() or not self._api_allowed():
            return
        path = urlsplit(self.path).path

        if path == "/api/login":
            return self._login()
        if path == "/api/noop":
            return self._send_noop()
        if match := COMMAND_VALIDATE.match(path):
            return self._validate_command(match["target"], match["name"])
        if match := COMMAND.match(path):
            return self._send_command(match["target"], match["name"])
        if match := RESEND.match(path):
            return self._resend(int(match["id"]))

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
            # A launch may rebuild the COSMOS plugin, so command definitions can change
            catalog.clear()
            self._send_json(202, {"state": launcher.state})
        else:
            self._send_json(409, {"error": "Busy"})

    def _login(self):
        """Check the password with COSMOS via CosmosJSONAPIClient.authenticate."""
        try:
            password = self._read_json().get("password", "")
        except ValueError as err:
            return self._send_json(400, {"error": str(err)})

        try:
            cosmos.authenticate(password)
        except NotAuthenticated:
            return self._send_json(401, {"error": "Wrong password."})
        except CosmosError as err:
            return self._send_cosmos_error(err)
        self._send_json(200, {"loggedIn": True})

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
