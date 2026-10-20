from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent

HOST = "127.0.0.1"
PORT = 3000
ALLOWED_HOSTS = [f"localhost:{PORT}", f"127.0.0.1:{PORT}"]

COSMOS_URL = "http://localhost:2900"
COSMOS_TIMEOUT_S = 5 * 60
COSMOS_POLL_S = 3
COSMOS_REQUEST_TIMEOUT_S = 2

CONTAINER = "nos3-desktop"
CONTAINER_USER = "jstar"
BACKEND_DIR = ROOT_DIR / "backend"
NOS3_DIR = "/home/jstar/nos3"
OPENC3_DIR = "/home/jstar/.nos3/openc3"

SETUP_TIMEOUT_S = 2 * 60 * 60
LAUNCH_TIMEOUT_S = 10 * 60
STOP_TIMEOUT_S = 3 * 60

STATIC_FILES = {
    "/": ("index.html", "text/html"),
    "/index.html": ("index.html", "text/html"),
    "/main.js": ("main.js", "text/javascript"),
}
