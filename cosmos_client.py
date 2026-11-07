import urllib.request as requests
import json

from constants import COSMOS_URL, COSMOS_API_URL, POST, HEADERS, TIMEOUT_S


class CosmosJSONAPIClient:

    def __init__(self):
        self._token = None
        self._opener = requests.build_opener(requests.ProxyHandler({}))

    def authenticate(self, password):
        body = json.dumps({"token": password}).encode()
        request = requests.Request(
            COSMOS_URL + "/openc3-api/auth/verify",
            data=body,
            headers=HEADERS,
            method=POST
        )

        with self._opener.open(request, timeout=TIMEOUT_S) as res:
            self._token = res.read().decode().strip()

    def send_command(self, target, packet):
        """Send a command with no parameters, e.g. ("GENERIC_MAG_DEBUG", "GENERIC_MAG_NOOP_CC").

        Raises PermissionError if not logged in, RuntimeError if COSMOS rejects it.
        """
        if self._token is None:
            raise PermissionError("Not logged in")

        body = json.dumps({
            "jsonrpc": "2.0",
            "method": "cmd",
            "params": [f"{target} {packet}"],
            "keyword_params": {"scope": "DEFAULT"},
            "id": 1,
        }).encode()
        request = requests.Request(
            COSMOS_API_URL,
            data=body,
            headers={"Content-Type": "application/json-rpc", "Authorization": self._token},
            method=POST
        )

        with self._opener.open(request, timeout=TIMEOUT_S) as res:
            reply = json.loads(res.read())
        if "error" in reply:
            raise RuntimeError(reply["error"].get("message", str(reply["error"])))
        return reply.get("result")




    
