"""
Reads the configuration of the current (most recently configured) simulation.
"""

import xml.etree.ElementTree as ET
from pathlib import PurePosixPath

from constants import BACKEND_DIR, NOS3_DIR
from default_config import CFG_DIR, ConfigError, _read_spacecraft, _text

CURRENT_CONFIG_PATH_FILE = CFG_DIR / "build" / "current_config_path.txt"


def _current_mission_file():
    """The mission file the last `make config` applied, as a host path."""

    if not CURRENT_CONFIG_PATH_FILE.is_file():
        raise ConfigError("No simulation configured yet.")

    container_path = PurePosixPath(
        CURRENT_CONFIG_PATH_FILE.read_text().strip())

    try:
        relative = container_path.relative_to(NOS3_DIR)
    except ValueError:
        raise ConfigError(f"Unexpected configuration path: {
                          container_path}") from None

    path = BACKEND_DIR / relative

    if not path.is_file():
        raise ConfigError(
            f"Current configuration not found: backend/{relative}")

    return path


def load_enabled_components():
    """Enabled components per spacecraft, sent as JSON by GET /api/components."""

    mission_file = _current_mission_file()

    try:
        mission = ET.parse(mission_file).getroot()

        sc_cfg = _text(mission, "sc-1-cfg")

        sc = _read_spacecraft(1, sc_cfg)
        spacecraft = {
            "name": sc["name"],
            "config": sc["config"],
            "components": [{"key": c["key"], "name": c["name"]} for c in sc["components"] if c["enabled"]],
        }
    except (ET.ParseError, ValueError, OSError) as err:
        raise ConfigError(
            f"Couldn't read the current configuration: {err}") from err
    return {"spacecraft": spacecraft}
