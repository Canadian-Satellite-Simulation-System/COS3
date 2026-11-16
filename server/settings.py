from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent

HOST = "127.0.0.1"
PORT = 3000
ALLOWED_HOSTS = [f"localhost:{PORT}", f"127.0.0.1:{PORT}"]

COSMOS_URL = "http://localhost:2900"
COSMOS_API_URL = COSMOS_URL + "/openc3-api/api"
COSMOS_AUTH_URL = COSMOS_URL + "/openc3-api/auth/verify"
COSMOS_SCOPE = "DEFAULT"
COSMOS_API_TIMEOUT_S = 15
COSMOS_PING_TIMEOUT_S = 2
COSMOS_START_TIMEOUT_S = 5 * 60
COSMOS_POLL_S = 3

CONTAINER = "nos3-desktop"
CONTAINER_USER = "jstar"
# The NOS3 submodule on the host (mounted at NOS3_DIR in the container)
NOS3_REPO_DIR = ROOT_DIR / "nos3"
NOS3_DIR = "/home/jstar/nos3"
USER_NOS3_DIR = "/home/jstar/.nos3"
# Created by `make prep`
NOS3_42_DIR = f"{USER_NOS3_DIR}/42"
# Created by `make gsw` (COSMOS / OpenC3)
OPENC3_DIR = f"{USER_NOS3_DIR}/openc3"

SETUP_TIMEOUT_S = 2 * 60 * 60
LAUNCH_TIMEOUT_S = 10 * 60
STOP_TIMEOUT_S = 3 * 60
