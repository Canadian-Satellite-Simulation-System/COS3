"""
Applies a custom configuration (scenario, components, start time, duration, orbit,
tipoff, 42 graphics window, 42 ground stations) without changing any file tracked in the backend repo.
Everything is written to backend/cfg/build/, which git ignores.

  1. write_spacecraft()    copy of the default spacecraft XML with our components, tipoff and 42 window,
                           passed to `make config SC1_CFG=build/cos3-sc-1.xml` (option built into NOS3)
  2. patch_after_config()  after `make config`: the scenario's 42 files (like configure.py does),
                           then start time, duration, orbit and ground stations in the generated 42 files
                           (Inp_Sim.txt, Orb_*.txt) and simulator file (nos3-simulator.xml)
"""

import datetime
import shutil
import xml.etree.ElementTree as ET

from constants import BACKEND_DIR
from default_config import SCENARIOS, _read_orbit, _read_sim

CFG_DIR = BACKEND_DIR / "cfg"
BUILD_DIR = CFG_DIR / "build"

# Passed to make config as SC1_CFG (path relative to backend/cfg/)
SPACECRAFT_FILE = "build/cos3-sc-1.xml"

# Same epoch as backend/scripts/cfg/configure.py (J2000 seconds <-> UTC)
J2000 = datetime.datetime(2000, 1, 1, 12, 0)
TIME_FORMAT = "%Y-%m-%d %H:%M:%S"
MIN_DURATION_S = 60
MAX_DURATION_S = 365 * 86400
MIN_ALTITUDE_KM = 100
MAX_ALTITUDE_KM = 100000
MAX_TIPOFF_DEG_S = 30
MAX_GROUND_STATIONS = 50
# 42 world names for ground stations (Inp_Sim.txt "Ground Stations" section)
STATION_WORLDS = {"Earth": "EARTH", "Luna": "LUNA"}


def _default_spacecraft_path():
    """The spacecraft file the default mission uses (<sc-1-cfg> in nos3-mission.xml)."""
    mission = ET.parse(CFG_DIR / "nos3-mission.xml").getroot()
    return CFG_DIR / mission.find("sc-1-cfg").text.strip()


def component_keys():
    """Component names known to NOS3 (adcs, cam, css, ...)."""
    root = ET.parse(_default_spacecraft_path()).getroot()
    return [c.tag for c in root.findall("components/*")]


def validate(values):
    """Check the values sent by the UI. Returns them cleaned up, or raises ValueError."""
    if not isinstance(values, dict):
        raise ValueError("Invalid configuration.")

    try:
        start = datetime.datetime.strptime(str(values.get("startUtc", "")).strip(), TIME_FORMAT)
    except ValueError:
        raise ValueError("Start time must look like 2025-10-20 17:43:20 (UTC).") from None

    try:
        duration = float(values.get("durationS"))
    except (TypeError, ValueError):
        raise ValueError("Duration must be a number.") from None
    if not MIN_DURATION_S <= duration <= MAX_DURATION_S:
        raise ValueError("Duration must be between 1 minute and 365 days.")

    components = values.get("components")
    known = component_keys()
    if not isinstance(components, dict) or any(k not in known for k in components):
        raise ValueError("Unknown component in the configuration.")

    scenario = values.get("scenario", "STF1")
    if scenario not in SCENARIOS:
        raise ValueError("Unknown scenario.")

    # Orbit values only apply to scenarios with a two-body (CENTRAL) orbit
    orbit = None
    if scenario_orbit_editable(scenario) and values.get("orbit") is not None:
        orbit = values["orbit"]
        periapsis = _number(orbit.get("periapsisKm"), "Periapsis")
        apoapsis = _number(orbit.get("apoapsisKm"), "Apoapsis")
        inclination = _number(orbit.get("inclinationDeg"), "Inclination")
        if not MIN_ALTITUDE_KM <= periapsis <= apoapsis <= MAX_ALTITUDE_KM:
            raise ValueError(
                f"Altitudes must be between {MIN_ALTITUDE_KM} and {MAX_ALTITUDE_KM} km, periapsis <= apoapsis."
            )
        if not 0 <= inclination <= 180:
            raise ValueError("Inclination must be between 0 and 180 degrees.")
        orbit = {"periapsisKm": periapsis, "apoapsisKm": apoapsis, "inclinationDeg": inclination}

    tipoff = values.get("tipoffDegS")
    if not isinstance(tipoff, list) or len(tipoff) != 3:
        raise ValueError("Tipoff needs 3 values (x, y, z).")
    tipoff = [_number(v, "Tipoff") for v in tipoff]
    if any(abs(v) > MAX_TIPOFF_DEG_S for v in tipoff):
        raise ValueError(f"Tipoff values must be between -{MAX_TIPOFF_DEG_S} and {MAX_TIPOFF_DEG_S} deg/s.")

    stations = values.get("groundStations")
    if stations is not None:
        stations = _validate_stations(stations)

    return {
        "startUtc": start,
        "durationS": duration,
        "components": {k: bool(components.get(k)) for k in components},
        "scenario": scenario,
        "orbit": orbit,
        "tipoffDegS": tipoff,
        "graphics42": bool(values.get("graphics42", True)),
        "groundStations": stations,
    }


def _validate_stations(stations):
    """42 ground stations: markers in the 42 window, and the first one (#0) is the ground
    end of both 42 comm links (Inp_CommLink.txt), computed every step and sent to the radio
    sim. The radio sim ignores them while its close-criteria are "none" (nos3-simulator.xml).
    At least one is required: 42 reads station #0 even when the list is empty."""
    if not isinstance(stations, list) or not 1 <= len(stations) <= MAX_GROUND_STATIONS:
        raise ValueError(f"Ground stations: 1 to {MAX_GROUND_STATIONS}.")
    clean = []
    for st in stations:
        if not isinstance(st, dict):
            raise ValueError("Invalid ground station.")
        name = str(st.get("name", "")).strip()
        if not 1 <= len(name) <= 30 or '"' in name or "!" in name:
            raise ValueError('Ground station names: 1 to 30 characters, without " or !.')
        world = st.get("world", "Earth")
        if world not in STATION_WORLDS:
            raise ValueError(f"Ground station {name}: world must be Earth or Luna.")
        lat = _number(st.get("lat"), f"{name} latitude")
        lon = _number(st.get("lon"), f"{name} longitude")
        if not -90 <= lat <= 90 or not -180 <= lon <= 180:
            raise ValueError(f"Ground station {name}: latitude -90..90, longitude -180..180.")
        clean.append({"name": name, "world": world, "lat": lat, "lon": lon})
    return clean


def scenario_orbit_editable(scenario):
    """Whether the scenario's orbit is described by periapsis/apoapsis/inclination."""
    orbit = _read_orbit(_read_sim(scenario)["orbitFile"])
    return bool(orbit and orbit["editable"])


def _number(value, label):
    try:
        return float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{label} must be a number.") from None


def write_spacecraft(values):
    """Copy of the default spacecraft XML with only our values changed:
    components on/off, tipoff (initial rotation) and the 42 graphics window."""
    tree = ET.parse(_default_spacecraft_path())
    root = tree.getroot()

    def set_text(path, text):
        node = root.find(path)
        if node is not None:
            node.text = text

    for key, enabled in values["components"].items():
        set_text(f"components/{key}/enable", "true" if enabled else "false")
    for axis, value in zip("xyz", values["tipoffDegS"]):
        set_text(f"orbit/tipoff_{axis}", f"{value:g}")
    set_text("gui/enable", "true" if values["graphics42"] else "false")
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    tree.write(CFG_DIR / SPACECRAFT_FILE, encoding="utf-8", xml_declaration=True)


def _replace_line(path, marker, make_line):
    """Replace the first line containing `marker` (like configure.py does), keeping its line ending.
    make_line(old_values) returns the new line; old_values are the words before the '!' comment."""
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    for i, line in enumerate(lines):
        if marker in line:
            ending = line[len(line.rstrip("\r\n")):] or "\n"
            lines[i] = make_line(line.split("!", 1)[0].split()) + ending
            path.write_text("".join(lines), encoding="utf-8")
            return
    raise ValueError(f"'{marker}' not found in {path.name}")


def _orbit_file(sim):
    """Name of the 42 orbit file Inp_Sim.txt uses (e.g. Orb_LEO.txt)."""
    for line in sim.read_text(encoding="utf-8").splitlines():
        if "Input file name for Orb" in line:  # "Orb 0" or "Orb 1" depending on the scenario
            return line.split("!", 1)[0].split()[1]
    raise ValueError("Orbit file not found in Inp_Sim.txt")


def apply_scenario(scenario, graphics42):
    """Use the scenario's 42 files, as configure.py does for <scenario> in the mission file
    (make config always uses the default mission, so the scenario is applied here)."""
    in_out = CFG_DIR / "InOut"
    sim = BUILD_DIR / "InOut" / "Inp_Sim.txt"
    shutil.copyfile(in_out / f"Inp_Sim_{scenario}.txt", sim)
    shutil.copyfile(in_out / f"Inp_Graphics_{scenario}.txt", BUILD_DIR / "InOut" / "Inp_Graphics.txt")
    # configure.py turns the 42 window off in Inp_Sim.txt; redo it on the new file
    if not graphics42:
        _replace_line(sim, "Graphics Front End", lambda _: "FALSE                           !  Graphics Front End?")


def _write_ground_stations(sim, stations):
    """Replace the "Ground Stations" section of Inp_Sim.txt (count line + one line per station)."""
    lines = sim.read_text(encoding="utf-8").splitlines(keepends=True)
    for i, line in enumerate(lines):
        if "Number of Ground Stations" in line:
            old_count = int(line.split()[0])
            ending = line[len(line.rstrip("\r\n")):] or "\n"
            new = [f"{len(stations)}                                            ! Number of Ground Stations{ending}"]
            new += [
                f'TRUE  {STATION_WORLDS[st["world"]]}  {st["lon"]:g}  {st["lat"]:g}  "{st["name"]}"'
                f"  ! Exists, World, Lng, Lat, Label{ending}"
                for st in stations
            ]
            lines[i:i + 1 + old_count] = new
            sim.write_text("".join(lines), encoding="utf-8")
            return
    raise ValueError("'Number of Ground Stations' not found in Inp_Sim.txt")


def patch_after_config(values):
    """Scenario, start time, duration and orbit in the files `make config` generated in cfg/build/."""
    start, duration_s, orbit = values["startUtc"], values["durationS"], values["orbit"]
    sim = BUILD_DIR / "InOut" / "Inp_Sim.txt"
    apply_scenario(values["scenario"], values["graphics42"])
    if values.get("groundStations") is not None:
        _write_ground_stations(sim, values["groundStations"])
    _replace_line(sim, "Date (UTC)", lambda _: start.strftime("%m %d %Y") + "  !  Date (UTC) (Month, Day, Year)")
    _replace_line(sim, "Time (UTC)", lambda _: start.strftime("%H %M %S") + "  !  Time (UTC) (Hr,Min,Sec)")
    # Keep the step size, change only the duration
    _replace_line(
        sim,
        "Sim Duration",
        lambda old: f"{duration_s:.1f}   {old[1] if len(old) > 1 else '0.01'}   !  Sim Duration, Step Size [sec]",
    )

    seconds = (start - J2000).total_seconds()
    _replace_line(
        BUILD_DIR / "sims" / "nos3-simulator.xml",
        "<absolute-start-time>",
        lambda _: f"        <absolute-start-time>{seconds:.1f}</absolute-start-time>",
    )

    # Orbit: periapsis/apoapsis altitudes and inclination in the 42 orbit file
    if orbit is None:
        return
    orb = BUILD_DIR / "InOut" / _orbit_file(sim)
    _replace_line(
        orb,
        "Periapsis & Apoapsis Altitude",
        lambda _: f"{orbit['periapsisKm']:g}  {orbit['apoapsisKm']:g}   !  Periapsis & Apoapsis Altitude, km",
    )
    _replace_line(orb, "Inclination (deg)", lambda _: f"{orbit['inclinationDeg']:g}   !  Inclination (deg)")
