"""
Starts and stops NOS3 for the COS3 UI.

NOS3 runs inside the nos3-desktop container (backend/docker/run.sh): `make launch`
opens its terminal tabs and the 42 window on the container's virtual desktop
(http://localhost:6080/vnc.html), not on the user's screen.

Copied from server.py (the first launcher prototype), which will be removed.
"""

import subprocess
import threading
import time
import urllib.request

import custom_config
from constants import (
    BACKEND_DIR,
    CONTAINER,
    CONTAINER_USER,
    COSMOS_POLL_S,
    COSMOS_REQUEST_TIMEOUT_S,
    COSMOS_TIMEOUT_S,
    COSMOS_URL,
    LAUNCH_TIMEOUT_S,
    NOS3_DIR,
    OPENC3_DIR,
    ROOT_DIR,
    SETUP_TIMEOUT_S,
    STOP_TIMEOUT_S,
)

# First-time setup, in order. Each step runs only if its `test` check fails.
# (`make config` is not here: it runs on every launch, see Launcher.configure.)
SETUP_STEPS = [
    (["-d", OPENC3_DIR], "make prep", "Preparing NOS3 (first run, this can take a while)…"),
    (["-d", f"{NOS3_DIR}/fsw/build"], "make", "Building NOS3 (first run, this can take a while)…"),
]

# `make` installs these two config files into the build folders. Copy them again after
# each `make config`, so components and start time apply without rebuilding.
INSTALL_CONFIG = (
    "cp cfg/build/nos3_defs/cpu1_cfe_es_startup.scr fsw/build/exe/cpu1/cf/cfe_es_startup.scr"
    " && cp cfg/build/sims/nos3-simulator.xml sims/build/bin/nos3-simulator.xml"
)

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

    def configure(self, values):
        """`make config` with the default configuration (values=None) or a custom one
        (validated values from custom_config.validate)."""
        if values is None:
            self.stage = "Configuring NOS3 (default)…"
            code, _ = nos3_exec("make config", timeout=SETUP_TIMEOUT_S)
        else:
            self.stage = "Configuring NOS3 (custom)…"
            custom_config.write_spacecraft(values)
            code, _ = nos3_exec(f"make config SC1_CFG={custom_config.SPACECRAFT_FILE}", timeout=SETUP_TIMEOUT_S)
        if code != 0:
            raise LaunchError("`make config` failed.")
        if values is not None:
            custom_config.patch_after_config(values)

    def launch(self, values=None):
        """Start the container, apply the configuration, run any missing setup,
        launch NOS3, and wait for COSMOS."""
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

        self.configure(values)

        for check, command, stage in SETUP_STEPS:
            self.stage = "Checking setup…"
            done, _ = run(["docker", "exec", CONTAINER, "test", *check])
            if done == 0:
                continue

            self.stage = stage
            code, _ = nos3_exec(command, timeout=SETUP_TIMEOUT_S)
            if code != 0:
                raise LaunchError(f"`{command}` failed.")

        self.stage = "Applying configuration…"
        code, _ = nos3_exec(INSTALL_CONFIG)
        if code != 0:
            raise LaunchError("Couldn't copy the configuration into the NOS3 build folders.")

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
