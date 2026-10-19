# Working with the COS3-backend submodule

COS3 is split across two repositories:

| Repo | Contents |
|---|---|
| **COS3** (this repo) | Docs, requirements, wizard and UI, HIL firmware, end-to-end tests |
| **COS3-backend** | Our fork of NOS3, including our component and configuration changes |

The backend lives in the `backend/` folder as a git submodule. 

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

Skipping the second command leaves `backend/` on an old commit, and `git status` will show it as modified.

## Change the backend

Backend changes are committed in two steps: first in the backend, then in COS3 so it points to the new commit.

```bash
cd backend
git checkout -b my-feature        # work on a branch, not a detached HEAD
# ...edit files...
git add -A
git commit -m "Describe the change"
git push -u origin my-feature

cd ..
git add backend                   # records the new backend commit in COS3
git commit -m "Update backend: describe the change"
git push
```

Forgetting the last three commands is the most common mistake: the backend is pushed, but COS3 still points at the old commit, so teammates don't receive the change.

## Run the simulation

Run the NOS3 commands from inside the backend folder:

```bash
cd backend
./docker/run.sh
```

Then follow the steps in the [backend](https://github.com/Canadian-Satellite-Simulation-System/COS3-backend) README to launch from the simulator.
