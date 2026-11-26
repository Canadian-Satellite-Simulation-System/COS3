"""
Starts and stops NOS3 for the COS3 UI.
"""

import subprocess
import threading
import time

from server.cosmos_client import cosmos_up
from server.mission_config import custom
from server.settings import (
    CONTAINER,
    CONTAINER_USER,
    COSMOS_POLL_S,
    COSMOS_START_TIMEOUT_S,
    COSMOS_URL,
    LAUNCH_TIMEOUT_S,
    NOS3_REPO_DIR,
    NOS3_42_DIR,
    NOS3_DIR,
    OPENC3_DIR,
    ROOT_DIR,
    SETUP_TIMEOUT_S,
    STOP_TIMEOUT_S,
)

# First-time setup, in order. Each step runs only if the folder it creates is missing.
# (`make config` is not here: it runs on every launch, see Launcher.configure.)
# `make` also runs `make gsw`, so the COSMOS step only runs when the flight software
# is built but COSMOS isn't installed (e.g. the nos3-home volume was reset).
SETUP_STEPS = [
    (["-d", NOS3_42_DIR], "make prep", "Preparing NOS3 (first run, this can take a while)…"),
    (["-d", f"{NOS3_DIR}/fsw/build"], "make", "Building NOS3 (first run, this can take a while)…"),
    (["-d", OPENC3_DIR], "make gsw", "Installing COSMOS (first run, this can take a while)…"),
]

# `make` installs these two config files into the build folders. Copy them again after
# each `make config`, so components and start time apply without rebuilding.
INSTALL_CONFIG = (
    "cp cfg/build/nos3_defs/cpu1_cfe_es_startup.scr fsw/build/exe/cpu1/cf/cfe_es_startup.scr"
    " && cp cfg/build/sims/nos3-simulator.xml sims/build/bin/nos3-simulator.xml"
)

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


# Simulation speeds the header offers. The NOS3 time driver only doubles or halves its rate.
SPEEDS = [0.25, 0.5, 1, 2, 4, 8, 16, 32]

# Sends time-driver commands through NOS3's command-bus bridge (nos-sim-bridge, TCP 12020):
# one JSON line per command, forwarded to the time driver's "time-command" node.
TIME_COMMAND_SCRIPT = (
    'for c in "$@"; do printf \'{"node":"time-command","cmd":"%s"}\\n\' "$c"; done'
    " > /dev/tcp/127.0.0.1/12020"
)


def time_command(*commands):
    """Send PAUSE, UNPAUSE, DECREASE (2x faster) or INCREASE (2x slower) to the NOS3 time driver."""
    code, _ = run(
        ["docker", "exec", CONTAINER, "docker", "exec", "nos-sim-bridge", "bash", "-c", TIME_COMMAND_SCRIPT, "_", *commands],
        timeout=30,
    )
    if code != 0:
        raise LaunchError("Couldn't reach the NOS3 time driver.")


# Name of the running mission (git-ignored build folder)
MISSION_NAME_FILE = custom.BUILD_DIR / "cos3-mission-name.txt"


def _read_mission_name():
    try:
        return MISSION_NAME_FILE.read_text(encoding="utf-8").strip() or None
    except OSError:
        return None


def _write_mission_name(name):
    try:
        if name:
            MISSION_NAME_FILE.parent.mkdir(parents=True, exist_ok=True)
            MISSION_NAME_FILE.write_text(name, encoding="utf-8")
        else:
            MISSION_NAME_FILE.unlink(missing_ok=True)
    except OSError:
        pass


def container_running():
    """Whether the nos3-desktop container is up."""
    code, output = run(["docker", "ps", "-q", "--filter", f"name=^{CONTAINER}$"], capture=True)
    return code == 0 and output.strip() != ""


class Launcher:
    """Tracks simulation state and runs launch/stop one at a time in the background."""

    def __init__(self):
        self.lock = threading.Lock()
        # idle | starting | running | stopping | error
        self.state = "idle"
        self.stage = ""
        self.error = None
        self.container_up = False
        # Kept in a file too, so the header still shows it after a server restart
        self.mission_name = _read_mission_name()
        self.paused = False
        self.speed = 1

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
            "missionName": self.mission_name,
            "paused": self.paused,
            "speed": self.speed,
        }

    def _check_running(self):
        if self.state != "running":
            raise LaunchError("The simulation isn't running.")

    def pause(self):
        self._check_running()
        time_command("PAUSE")
        self.paused = True

    def resume(self):
        self._check_running()
        time_command("UNPAUSE")
        self.paused = False

    def set_speed(self, speed):
        """Step the time driver up or down (x2 per command) to reach one of SPEEDS."""
        if speed not in SPEEDS:
            raise ValueError("Unknown speed.")
        self._check_running()
        steps = SPEEDS.index(speed) - SPEEDS.index(self.speed)
        if steps:
            time_command(*(["DECREASE"] * steps if steps > 0 else ["INCREASE"] * -steps))
        self.speed = speed

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
        (validated values from custom.validate)."""
        if values is None:
            self.stage = "Configuring NOS3 (default)…"
            code, _ = nos3_exec("make config", timeout=SETUP_TIMEOUT_S)
        else:
            self.stage = "Configuring NOS3 (custom)…"
            custom.write_spacecraft(values)
            code, _ = nos3_exec(f"make config SC1_CFG={custom.SPACECRAFT_FILE}", timeout=SETUP_TIMEOUT_S)
        if code != 0:
            raise LaunchError("`make config` failed.")
        if values is not None:
            custom.patch_after_config(values)

    def launch(self, values=None, mission_name=None):
        """Start the container, apply the configuration, run any missing setup,
        launch NOS3, and wait for COSMOS."""
        self.mission_name = mission_name
        _write_mission_name(mission_name)
        self.paused = False
        self.speed = 1
        was_running = container_running()
        if was_running and cosmos_up():
            self.container_up = True
            self.state = "running"
            return

        if not was_running:
            self.stage = "Starting container…"
            code, _ = run([str(NOS3_REPO_DIR / "docker" / "run.sh")])
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
        deadline = time.monotonic() + COSMOS_START_TIMEOUT_S
        while not cosmos_up():
            if time.monotonic() > deadline:
                raise LaunchError(f"COSMOS didn't respond at {COSMOS_URL} within {COSMOS_START_TIMEOUT_S // 60} minutes.")
            time.sleep(COSMOS_POLL_S)
        self.state = "running"

    def stop(self):
        """Stop NOS3, then kill the container."""
        if container_running():
            self.stage = "Stopping NOS3…"
            nos3_exec("make stop", timeout=STOP_TIMEOUT_S)

        self.stage = "Stopping container…"
        code, _ = run([str(NOS3_REPO_DIR / "docker" / "stop.sh")])
        if code != 0:
            raise LaunchError("Couldn't stop the nos3-desktop container.")
        self.container_up = False
        self.mission_name = None
        _write_mission_name(None)
        self.paused = False
        self.speed = 1
        self.state = "idle"


launcher = Launcher()
