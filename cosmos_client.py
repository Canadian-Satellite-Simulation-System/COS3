import itertools
import json
import threading
import urllib.error
import urllib.request

from constants import COSMOS_API_URL, COSMOS_URL, TIMEOUT_S

AUTH_URL = COSMOS_URL + "/openc3-api/auth/verify"
SCOPE = "DEFAULT"


class CosmosError(Exception):
    """Base class: any COSMOS failure. The message is safe to show on the page."""


class NotAuthenticated(CosmosError):
    """No session, or COSMOS rejected the token/password. -> 401"""


class CosmosUnavailable(CosmosError):
    """COSMOS isn't reachable (not launched, or still starting). -> 502"""


class CosmosRejected(CosmosError):
    """COSMOS answered with a JSON-RPC error (unknown packet, out of range, ...). -> 400"""

    def __init__(self, message, error_class=None):
        super().__init__(message)
        self.error_class = error_class


class HazardousCommand(CosmosRejected):
    """The command is hazardous and was sent without the no-hazardous-check variant."""


class CosmosJSONAPIClient:
    def __init__(self, api_url=COSMOS_API_URL, auth_url=AUTH_URL, timeout=TIMEOUT_S):
        self._api_url = api_url
        self._auth_url = auth_url
        self._timeout = timeout
        self._token = None
        self._lock = threading.Lock()
        self._ids = itertools.count(1)
        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    # Session:

    def authenticate(self, password):
        """Exchange the password for a session token. Raises NotAuthenticated if wrong."""
        token = self._post(self._auth_url, {"token": password}, {"Content-Type": "application/json"})
        with self._lock:
            self._token = token.strip()

    @property
    def authenticated(self):
        return self._token is not None

    # JSON

    def call(self, method, *params, **keyword_params):
        """Call any COSMOS API method"""

        with self._lock:
            token = self._token

        if token is None:
            raise NotAuthenticated()

        body = {
            "jsonrpc": "2.0",
            "method": method,
            "params": list(params),
            "keyword_params": {"scope": SCOPE, **keyword_params},
            "id": next(self._ids),
        }
        reply = json.loads(self._post(
            self._api_url, body, {"Content-Type": "application/json-rpc", "Authorization": token}
        ))

        if "error" in reply:
            error = reply["error"]
            message = error.get("message", str(error))
            error_class = (error.get("data") or {}).get("class")
            exc = HazardousCommand if error_class == "HazardousError" else CosmosRejected
            raise exc(message, error_class)

        return reply.get("result")

    # COSMOS Methods

    def get_target(self, target):
        """Target info; includes "ignored_parameters" (the CCSDS header fields)."""
        return self.call("get_target", target)

    def get_all_cmds(self, target):
        """Every command definition for a target, with its parameters."""
        return self.call("get_all_cmds", target)

    def get_cmd(self, target, name):
        """One command definition."""
        return self.call("get_cmd", target, name)

    def send_command(self, target, name, params=None):
        return self.call("cmd", target, name, params or {})

    # HTTP Methods

    def _post(self, url, body, headers):
        """POST JSON, return the response text. Maps transport failures to CosmosError types."""
        request = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers, method="POST")
        try:
            with self._opener.open(request, timeout=self._timeout) as res:
                return res.read().decode()

        except urllib.error.HTTPError as err:
            if err.code == 401:
                with self._lock:
                    self._token = None 
                raise NotAuthenticated() from err

            raise CosmosError(f"COSMOS returned HTTP {err.code}.") from err
        except OSError as err:
            raise CosmosUnavailable("Can't reach COSMOS. Is it running?") from err
