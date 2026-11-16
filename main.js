const COSMOS_URL = "http://localhost:2900";
const POLL_MS = 2000;

const launchButton = document.getElementById("launch-button");
const stopButton = document.getElementById("stop-button");
const statusText = document.getElementById("status");
const spinner = document.getElementById("spinner");
const loginForm = document.getElementById("login-form");
const passwordInput = document.getElementById("password");
const loginError = document.getElementById("login-error");
const launcher = document.getElementById("launcher");

let current = { state: "idle" };
let pollTimer = null;

async function api(method, path, body) {
  // The launcher rejects API requests without this header
  const headers = { "X-COS3": "1" };
  if (body) headers["Content-Type"] = "application/json";
  const res = await fetch(path, { method, headers, body: body && JSON.stringify(body) });
  return res.json();
}

loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  loginError.textContent = "";
  try {
    const result = await api("POST", "/api/login", { password: passwordInput.value });
    if (!result.loggedIn) {
      loginError.textContent = result.error || "Login failed.";
      return;
    }
  } catch {
    loginError.textContent = "Can't reach the launcher. Is `python3 server.py` running?";
    return;
  }
  loginForm.hidden = true;
  launcher.hidden = false;
  showLauncher();
});

function isBusy(state) {
  return state === "starting" || state === "stopping";
}

function render(status) {
  const busy = isBusy(status.state);

  launchButton.textContent = status.state === "running" ? "Open COSMOS" : "Launch Simulation";
  launchButton.disabled = busy;
  stopButton.disabled = busy || !status.containerRunning;
  spinner.hidden = !busy;

  if (busy) {
    statusText.textContent = status.stage;
  } else if (status.state === "error") {
    statusText.textContent = status.error;
  } else if (status.state === "running") {
    statusText.textContent = "Simulation is running.";
  } else {
    statusText.textContent = "";
  }
}

async function refresh() {
  try {
    current = await api("GET", "/api/status");
  } catch {
    current = { state: "error", error: "Can't reach the launcher. Is `python3 server.py` running?" };
  }
  render(current);
  return current;
}

// Poll until the current operation finishes, then call onDone with the result
function poll(onDone) {
  clearTimeout(pollTimer);
  pollTimer = setTimeout(async () => {
    const status = await refresh();
    if (isBusy(status.state)) {
      poll(onDone);
    } else if (onDone) {
      onDone(status);
    }
  }, POLL_MS);
}

async function start() {
  if (current.state === "running") {
    window.location.href = COSMOS_URL;
    return;
  }

  render({ ...current, state: "starting", stage: "Starting…" });
  await api("POST", "/api/launch");
  poll((status) => {
    if (status.state === "running") {
      window.location.href = COSMOS_URL;
    }
  });
}

async function stop() {
  if (!confirm("Stop the simulation?")) return;

  render({ ...current, state: "stopping", stage: "Stopping…" });
  await api("POST", "/api/stop");
  poll();
}

function showLauncher() {
  refresh().then((status) => {
    // Pick up an operation that was already in progress when the page loaded
    if (isBusy(status.state)) poll();
  });
}
