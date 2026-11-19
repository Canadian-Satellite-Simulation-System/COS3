# COS3

COS3 is split across two repositories:

| Repo | Contents |
|---|---|
| **COS3** (this repo) | Docs, requirements, wizard and UI, HIL firmware, end-to-end tests |
| **COS3-backend** | Our fork of NOS3, including our component and configuration changes |

The backend lives in the `nos3/` folder as a git submodule.

## Project layout

```
nos3/      NOS3 fork (COS3-backend submodule)
server/    Python API: app.py (HTTP routes), commands/, telemetry/, mission_config/, simulation.py
ui/        pages/ (HTML) and assets/ (js/, css/)
tests/     unit tests: python3 -m unittest
main.py    entry point: python3 main.py
```

## Clone the project

```bash
git clone --recurse-submodules git@github.com:Canadian-Satellite-Simulation-System/COS3.git
cd COS3
```

## Get the latest changes

```bash
git pull
git submodule update --init --recursive
```

Skipping the second command leaves `nos3/` on an old commit, and `git status` will show it as modified.

## Change the backend

Backend changes are committed in two steps: first in the backend, then in COS3 so it points to the new commit.

```bash
cd nos3
git checkout -b my-feature        # work on a branch, not a detached HEAD
# ...edit files...
git add -A
git commit -m "Describe the change"
git push -u origin my-feature

cd ..
git add nos3                      # records the new backend commit in COS3
git commit -m "Update backend: describe the change"
git push
```

Forgetting the last three commands is the most common mistake: the backend is pushed, but COS3 still points at the old commit, so teammates don't receive the change.

## Run the UI

The COS3 UI (the wireframe pages in `ui/`) is served by `server/app.py`. Run it from the terminal, with Docker Desktop running:

```bash
python3 main.py
```

Open http://localhost:3000. On the Setup Wizard, the **Default configuration** tab has a working **Launch simulation** button:

- It starts the `nos3-desktop` container, runs `make config`, then any missing setup (`make prep`, `make`, `make gsw` for COSMOS), then `make launch`. The logic is in `server/simulation.py`.
- Until a simulation runs, the sidebar shows only the Setup Wizard. Once COSMOS responds (http://localhost:2900), the page switches to the Dashboard and the sidebar shows the simulation pages instead of the wizard.
- NOS3's terminal tabs and the 42 window open on the container's virtual desktop, not on your screen: http://localhost:6080/vnc.html.
- **■ Stop** in the header runs `make stop` and stops the container, then the page returns to the Setup Wizard.

Notes:

- Stop any NOS3 you started by hand first (`make stop`), otherwise ports 2900 and 6080 are already taken.
- The first launch builds NOS3 inside the container and can take a long time.

### First-time setup

On the first launch, the launcher also runs `make prep`, `make` and `make gsw` inside the container, skipping any step that has already been done. This pulls several GB of images and builds everything, so it can take a while; give Docker Desktop at least 8 GB RAM and 4 CPUs. See the [backend](https://github.com/Canadian-Satellite-Simulation-System/COS3-backend) README and [docker/README.md](nos3/docker/README.md) for details.
