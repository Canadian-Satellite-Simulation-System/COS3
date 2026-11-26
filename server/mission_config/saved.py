"""
Saved mission configurations: JSON files in configs/ at the repo root, committed with git
so everyone on the team can launch them. Each file holds the wizard values (see custom.validate).
"""

import datetime
import json
import re

from server.mission_config import custom
from server.settings import ROOT_DIR

SAVED_DIR = ROOT_DIR / "configs"
FILE_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+\.json$")
MAX_NAME_LENGTH = 60


def save(name, values):
    """Validate and write a configuration. Returns {file, config}, or raises ValueError."""
    name = str(name or "").strip()
    if not name:
        raise ValueError("Enter a mission name to save the configuration.")
    if len(name) > MAX_NAME_LENGTH:
        raise ValueError(f"Mission name must be at most {MAX_NAME_LENGTH} characters.")
    custom.validate(values)

    now = datetime.datetime.now(datetime.timezone.utc)
    slug = re.sub(r"[^A-Za-z0-9]+", "-", name).strip("-") or "mission"
    base = f"{slug}_{now:%Y-%m-%d}"
    file = f"{base}.json"
    n = 2
    while (SAVED_DIR / file).exists():
        file = f"{base}-{n}.json"
        n += 1

    config = {"missionName": name, "savedAt": now.isoformat(timespec="seconds"), "values": values}
    SAVED_DIR.mkdir(exist_ok=True)
    (SAVED_DIR / file).write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    return {"file": file, "config": config}


def load(file):
    """One saved configuration. Raises ValueError if the name is invalid or the file is unreadable."""
    if not FILE_PATTERN.match(file):
        raise ValueError("Invalid configuration file name.")
    try:
        return json.loads((SAVED_DIR / file).read_text(encoding="utf-8"))
    except (OSError, ValueError) as err:
        raise ValueError(f"Couldn't read {file}.") from err


def list_saved():
    """Summaries of all saved configurations, newest first (unreadable files are skipped)."""
    configs = []
    for path in SAVED_DIR.glob("*.json") if SAVED_DIR.is_dir() else []:
        try:
            config = load(path.name)
            values = config["values"]
        except (ValueError, KeyError, TypeError):
            continue
        configs.append({
            "file": path.name,
            "missionName": config.get("missionName", path.stem),
            "savedAt": config.get("savedAt", ""),
            "components": sum(1 for on in (values.get("components") or {}).values() if on),
            "groundStations": len(values.get("groundStations") or []),
        })
    return sorted(configs, key=lambda c: c["savedAt"], reverse=True)
