"""
Reads the default NOS3 configuration from the backend, for display in the Setup Wizard.

Read only: nothing is written. These are the same files `make config` uses
(backend/scripts/cfg/configure.py) when no SC1_CFG is given:

  backend/cfg/nos3-mission.xml               mission: start time, fsw, gsw, scenario, spacecraft
  backend/cfg/spacecraft/sc-*-config.xml     spacecraft: cFS applications and components on/off
  backend/cfg/InOut/Inp_Sim_<scenario>.txt   42: duration, step, ground stations, orbit file
  backend/cfg/InOut/Orb_*.txt                42: orbit description, altitudes, inclination
"""

import datetime
import re
import xml.etree.ElementTree as ET

from constants import BACKEND_DIR

CFG_DIR = BACKEND_DIR / "cfg"
MISSION_FILE = CFG_DIR / "nos3-mission.xml"

# NOS3 scenarios (<scenario> in nos3-mission.xml). Same scenario -> 42 file mapping as
# configure.py: cfg/InOut/Inp_Sim_<key>.txt and Inp_Graphics_<key>.txt
SCENARIOS = {
    "STF1": "Low Earth orbit (NASA STF-1 CubeSat)",
    "Gateway": "Lunar Gateway orbit (NRHO, Earth-Moon)",
    "DeepSpace": "Low lunar orbit, Deep Space Network stations",
}
DEFAULT_SCENARIO = "STF1"


def scenario_sim_file(scenario):
    """The 42 Inp_Sim file of a scenario (configure.py falls back to STF1)."""
    return f"Inp_Sim_{scenario if scenario in SCENARIOS else DEFAULT_SCENARIO}.txt"

FSW_LABELS = {"cfs": "cFS", "fprime": "F Prime"}
GSW_LABELS = {
    "openc3": "OpenC3 COSMOS",
    "cosmos": "COSMOS 4",
    "yamcs": "YAMCS",
    "fprime": "F Prime GDS",
    "ait": "AIT",
    "multiple": "COSMOS + YAMCS",
}
COMPONENT_LABELS = {
    "adcs": "ADCS",
    "cam": "Camera",
    "css": "Coarse sun sensors",
    "eps": "Power (EPS)",
    "fss": "Fine sun sensor",
    "gps": "GPS receiver",
    "imu": "IMU",
    "mag": "Magnetometer",
    "mgr": "Mode manager",
    "onair": "OnAIR",
    "radio": "Radio",
    "rw": "Reaction wheels",
    "sample": "Sample",
    "st": "Star tracker",
    "syn": "Synopsis",
    "torquer": "Magnetorquers",
    "thruster": "Thruster",
}


class ConfigError(Exception):
    """A default configuration file is missing or unreadable; the message is shown on the page."""


def _text(root, path, default=None):
    node = root.find(path)
    return node.text.strip() if node is not None and node.text else default


def _is_true(value):
    return (value or "").strip().lower() == "true"


def _start_time_utc(seconds):
    # Same conversion as configure.py (J2000 seconds -> UTC)
    start = datetime.datetime(2000, 1, 1, 12, 0) + datetime.timedelta(seconds=float(seconds))
    return start.strftime("%Y-%m-%d %H:%M:%S")


def _duration_label(seconds):
    seconds = int(float(seconds))
    days, rest = divmod(seconds, 86400)
    hours, rest = divmod(rest, 3600)
    minutes = rest // 60
    parts = [f"{days} d" if days else "", f"{hours} h" if hours else "", f"{minutes} min" if minutes else ""]
    return " ".join(p for p in parts if p) or f"{seconds} s"


def _read_42_lines(path):
    """42 input files: one value per line, a '!' comment describing it."""
    if not path.is_file():
        return []
    return path.read_text(encoding="utf-8", errors="replace").splitlines()


def _value_before(lines, comment):
    """Values on the first line whose comment contains `comment` (case-insensitive)."""
    for line in lines:
        if "!" in line and comment.lower() in line.split("!", 1)[1].lower():
            return line.split("!", 1)[0].split()
    return None


def _read_sim(scenario):
    """Duration, step, orbit file and ground stations from the scenario's 42 Inp_Sim file."""
    sim_file = scenario_sim_file(scenario)
    lines = _read_42_lines(CFG_DIR / "InOut" / sim_file)

    duration = _value_before(lines, "Sim Duration")
    # "Orb 0" in STF1/Gateway, "Orb 1" in DeepSpace
    orbit = _value_before(lines, "Input file name for Orb")

    stations = []
    for line in lines:
        # e.g.  TRUE  EARTH  -77.0  37.0  "GSFC"   ! Exists, World, Lng, Lat, Label
        m = re.match(r'\s*(TRUE|FALSE)\s+(\w+)\s+(-?[\d.]+)\s+(-?[\d.]+)\s+"([^"]*)"', line)
        if m and _is_true(m.group(1)):
            stations.append({
                "name": m.group(5),
                "world": m.group(2).capitalize(),
                "lon": float(m.group(3)),
                "lat": float(m.group(4)),
            })

    return {
        "file": sim_file,
        "durationS": float(duration[0]) if duration else None,
        "duration": _duration_label(duration[0]) if duration else None,
        "stepS": float(duration[1]) if duration and len(duration) > 1 else None,
        "orbitFile": orbit[1] if orbit and len(orbit) > 1 else None,
        "groundStations": stations,
    }


def _read_orbit(orbit_file):
    """Description, altitudes and inclination from a 42 Orb_*.txt file."""
    if not orbit_file:
        return None
    lines = _read_42_lines(CFG_DIR / "InOut" / orbit_file)
    if not lines:
        return None
    desc = lines[1].split("!", 1)[0].strip() if len(lines) > 1 else orbit_file
    alts = _value_before(lines, "Periapsis & Apoapsis Altitude")
    inc = _value_before(lines, "Inclination")
    orbit_type = (_value_before(lines, "Orbit Type") or [""])[0]
    return {
        "file": orbit_file,
        "description": desc,
        "type": orbit_type,
        # Periapsis/apoapsis/inclination only describe a CENTRAL (two-body) orbit;
        # a THREE_BODY orbit (e.g. Gateway NRHO) is defined differently
        "editable": orbit_type == "CENTRAL",
        "center": (_value_before(lines, "Orbit Center") or [""])[0].capitalize(),
        "periapsisKm": float(alts[0]) if alts else None,
        "apoapsisKm": float(alts[1]) if alts and len(alts) > 1 else None,
        "inclinationDeg": float(inc[0]) if inc else None,
    }


def _read_spacecraft(index, sc_cfg):
    path = CFG_DIR / sc_cfg
    if not path.is_file():
        raise ConfigError(f"Spacecraft configuration not found: backend/cfg/{sc_cfg}")
    root = ET.parse(path).getroot()

    apps = [{"key": app.tag, "enabled": _is_true(_text(app, "enable"))} for app in root.findall("applications/*")]
    components = [
        {"key": c.tag, "name": COMPONENT_LABELS.get(c.tag, c.tag), "enabled": _is_true(_text(c, "enable"))}
        for c in root.findall("components/*")
    ]
    return {
        "name": f"SAT-{index}",
        "config": path.name,
        "applications": apps,
        "components": components,
        "graphics42": _is_true(_text(root, "gui/enable")),
        "tipoffDegS": [float(_text(root, f"orbit/tipoff_{axis}", "0")) for axis in "xyz"],
    }


def load_scenarios():
    """The scenarios a custom configuration can use, with their own 42 defaults."""
    scenarios = []
    for key, label in SCENARIOS.items():
        sim = _read_sim(key)
        scenarios.append({
            "key": key,
            "label": label,
            "simFile": sim["file"],
            "orbit": _read_orbit(sim["orbitFile"]),
            "groundStations": len(sim["groundStations"]),
            "stations": sim["groundStations"],
        })
    return scenarios


def load_default_config():
    """The default configuration as a dict (sent as JSON by GET /api/config/default)."""
    if not MISSION_FILE.is_file():
        raise ConfigError(
            "backend/cfg/nos3-mission.xml not found. Run `git submodule update --init --recursive`."
        )
    try:
        mission = ET.parse(MISSION_FILE).getroot()
        start = _text(mission, "start-time", "0")
        fsw = _text(mission, "fsw", "")
        gsw = _text(mission, "gsw", "")
        scenario = _text(mission, "scenario", "STF1")
        count = int(_text(mission, "number-spacecraft", "1"))

        spacecraft = []
        for i in range(1, count + 1):
            sc_cfg = _text(mission, f"sc-{i}-cfg")
            if sc_cfg:
                spacecraft.append(_read_spacecraft(i, sc_cfg))

        sim = _read_sim(scenario)
        scenarios = load_scenarios()
    except (ET.ParseError, ValueError, OSError) as err:
        raise ConfigError(f"Couldn't read the default configuration: {err}") from err

    return {
        "name": "Default configuration",
        "file": MISSION_FILE.name,
        "mission": {
            "startTimeUtc": _start_time_utc(start),
            "duration": sim["duration"],
            "durationS": sim["durationS"],
            "stepS": sim["stepS"],
            "scenario": scenario,
            "fsw": fsw,
            "fswLabel": FSW_LABELS.get(fsw, fsw),
            "gsw": gsw,
            "gswLabel": GSW_LABELS.get(gsw, gsw),
        },
        "spacecraft": spacecraft,
        "simFile": sim["file"],
        "scenarios": scenarios,
        "orbit": _read_orbit(sim["orbitFile"]),
        "groundStations": sim["groundStations"],
        "faultScenario": None,
        "hardwareInTheLoop": False,
    }


if __name__ == "__main__":
    import json

    print(json.dumps(load_default_config(), indent=2))
