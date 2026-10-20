"""
Local launcher for COS3.
Serves the UI and starts/stops the NOS3 desktop container and simulation.

Usage: python3 server.py   then open http://localhost:3000
"""

import json
import subprocess
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

from constants import (
    ALLOWED_HOSTS,
    BACKEND_DIR,
    CONTAINER,
    CONTAINER_USER,
    COSMOS_POLL_S,
    COSMOS_REQUEST_TIMEOUT_S,
    COSMOS_TIMEOUT_S,
    COSMOS_URL,
    HOST,
    LAUNCH_TIMEOUT_S,
    NOS3_DIR,
    OPENC3_DIR,
    PORT,
    ROOT_DIR,
    SETUP_TIMEOUT_S,
    STATIC_FILES,
    STOP_TIMEOUT_S,
)

# First-time setup, in order. Each step runs only if its `test` check fails.
SETUP_STEPS = [
    (["-f", f"{NOS3_DIR}/cfg/build/launch.sh"], "make config", "Configuring NOS3…"),
    (["-d", OPENC3_DIR], "make prep", "Preparing NOS3 (first run, this can take a while)…"),
    (["-d", f"{NOS3_DIR}/fsw/build"], "make", "Building NOS3 (first run, this can take a while)…"),
]

# Ignore any HTTP proxy settings when checking COSMOS on localhost
_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


class LaunchError(Exception):
    """A launch or stop step failed; the message is shown on the page."""


def run(args, timeout=None, capture=False):
    """Run a command, returning its exit code and (if captured) stdout."""
    try:
        result = subprocess.run(
            args,
            cwd=ROOT_DIR,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE if capture else subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired):
        return -1, ""
    return result.returncode, result.stdout or ""


def nos3_exec(command, env=(), timeout=None):
    """Run a shell command in the NOS3 repo inside the desktop container."""
    env_args = [arg for e in env for arg in ("-e", e)]
    return run(
        ["docker", "exec", "-u", CONTAINER_USER, *env_args, CONTAINER, "bash", "-lc", f"cd {NOS3_DIR} && {command}"],
        timeout=timeout,
    )


def container_running():
    """Whether the nos3-desktop container is up."""
    code, output = run(["docker", "ps", "-q", "--filter", f"name=^{CONTAINER}$"], capture=True)
    return code == 0 and output.strip() != ""


def cosmos_up():
    """Whether COSMOS answers at COSMOS_URL."""
    try:
        with _opener.open(COSMOS_URL, timeout=COSMOS_REQUEST_TIMEOUT_S) as res:
            return res.status < 400
    except OSError:
        return False


class Launcher:
    """Tracks simulation state and runs launch/stop one at a time in the background."""

    def __init__(self):
        self.lock = threading.Lock()
        # idle | starting | running | stopping | error
        self.state = "idle"
        self.stage = ""
        self.error = None
        self.container_up = False

    def is_busy(self):
        return self.state in ("starting", "stopping")

    def status(self):
        """Current state for GET /api/status."""
        self.refresh()
        return {
            "state": self.state,
            "stage": self.stage,
            "error": self.error,
            "containerRunning": self.container_up,
        }

    def refresh(self):
        """Re-detect state from Docker, so a page reload or server restart
        shows the simulation correctly if it was started earlier."""
        if self.is_busy():
            return
        self.container_up = container_running()
        if self.container_up and cosmos_up():
            self.state = "running"
            self.error = None
        elif self.state == "running":
            self.state = "idle"

    def begin(self, busy_state, operation):
        """Start an operation in a thread. Returns False if one is already running."""
        with self.lock:
            if self.is_busy():
                return False
            self.state = busy_state
            self.error = None
        threading.Thread(target=self._run_operation, args=(operation,), daemon=True).start()
        return True

    def _run_operation(self, operation):
        try:
            operation()
        except LaunchError as err:
            self.state = "error"
            self.error = str(err)
        except Exception as err:
            self.state = "error"
            self.error = f"Unexpected error: {err}"
        finally:
            self.stage = ""

    def launch(self):
        """Start the container, run any missing setup, launch NOS3, and wait for COSMOS."""
        was_running = container_running()
        if was_running and cosmos_up():
            self.container_up = True
            self.state = "running"
            return

        if not was_running:
            self.stage = "Starting container…"
            code, _ = run([str(BACKEND_DIR / "docker" / "run.sh")])
            if code != 0:
                raise LaunchError("Couldn't start the nos3-desktop container. Is Docker Desktop running?")
        self.container_up = True

        for check, command, stage in SETUP_STEPS:
            self.stage = "Checking setup…"
            done, _ = run(["docker", "exec", CONTAINER, "test", *check])
            if done == 0:
                continue

            self.stage = stage
            code, _ = nos3_exec(command, timeout=SETUP_TIMEOUT_S)
            if code != 0:
                raise LaunchError(f"`{command}` failed.")

        self.stage = "Launching NOS3…"
        code, _ = nos3_exec("make launch", env=["DISPLAY=:1"], timeout=LAUNCH_TIMEOUT_S)
        if code != 0:
            raise LaunchError("`make launch` failed.")

        self.stage = "Waiting for COSMOS…"
        deadline = time.monotonic() + COSMOS_TIMEOUT_S
        while not cosmos_up():
            if time.monotonic() > deadline:
                raise LaunchError(f"COSMOS didn't respond at {COSMOS_URL} within {COSMOS_TIMEOUT_S // 60} minutes.")
            time.sleep(COSMOS_POLL_S)
        self.state = "running"

    def stop(self):
        """Stop NOS3, then kill the container."""
        if container_running():
            self.stage = "Stopping NOS3…"
            nos3_exec("make stop", timeout=STOP_TIMEOUT_S)

        self.stage = "Stopping container…"
        code, _ = run([str(BACKEND_DIR / "docker" / "stop.sh")])
        if code != 0:
            raise LaunchError("Couldn't stop the nos3-desktop container.")
        self.container_up = False
        self.state = "idle"


launcher = Launcher()


class Handler(BaseHTTPRequestHandler):
    """Serves the UI files and the /api/status, /api/launch and /api/stop endpoints."""

    def do_GET(self):
        if not self._allowed():
            return
        path = urlsplit(self.path).path

        if path in STATIC_FILES:
            file, content_type = STATIC_FILES[path]
            body = (ROOT_DIR / file).read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif path == "/api/status":
            if self._api_allowed():
                self._send_json(200, launcher.status())
        else:
            self._send_json(404, {"error": "Not found"})

    def do_POST(self):
        if not self._allowed() or not self._api_allowed():
            return
        path = urlsplit(self.path).path

        operations = {
            "/api/launch": ("starting", launcher.launch),
            "/api/stop": ("stopping", launcher.stop),
        }
        if path not in operations:
            return self._send_json(404, {"error": "Not found"})

        if launcher.begin(*operations[path]):
            self._send_json(202, {"state": launcher.state})
        else:
            self._send_json(409, {"error": "Busy"})

    def _allowed(self):
        # Reject DNS rebinding and cross-site requests: the API runs local commands
        if self.headers.get("Host") not in ALLOWED_HOSTS:
            self._send_json(403, {"error": "Forbidden"})
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

    def log_message(self, format, *args):
        # The page polls /api/status every few seconds; keep the terminal quiet
        pass


def main():
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"COS3 launcher running at http://localhost:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
