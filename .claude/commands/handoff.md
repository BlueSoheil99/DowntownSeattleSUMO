Refresh HANDOFF.md so that a fresh context (a new session, compaction, or /clear) can pick up the work. Save it as HANDOFF.md in the repo root, overwriting it. Afterward, reply with a 3-line summary of what changed, not the full file (unless I ask).

Before writing, check the current state of the repo directly: run `git log --oneline -30`, `git status`, and list the directory tree (skip large generated outputs). Base the handoff on what's actually in the repo, plus what we did in this conversation. Don't rely on memory alone.

Structure it exactly like this:

## 1. Role (write this as instructions addressed to the new Claude)
You are a lab/research assistant helping build a digital twin of downtown Seattle in SUMO with multiple transit modes. Your responsibilities:
- Write and maintain Python scripts for importing maps (OSM), travel demand, ridership, GTFS bus routes/stops, and other inputs.
- Edit .net.xml and related network files so the street network matches real life (lanes, turn restrictions, signals, bus lanes, stops).
- Give technical feedback, and explain any pipeline in the project in detail when asked.
- Keep the working log and README files up to date as changes are made.
- Ask before making destructive changes (deleting files, regenerating the network, force-pushing).

## 2. Project status snapshot
- What works right now, and how to run it (exact commands, config file names, OS notes: I work on Windows and Mac).
- What's broken, partly done, or untested.
- The most recent task we were working on, and the next 3–5 concrete steps.

## 3. Repo structure
An annotated tree of the important directories and files, one line on what each is for. Point out which files are generated (and by which script) versus edited by hand.

## 4. Pipelines
For each pipeline (network build, demand/routes, GTFS/transit, simulation run, outputs/analysis): its inputs, the script(s), its outputs, the order to run them, and key parameters or assumptions.

## 5. Change history
- Python scripts: what changed in each one and why, newest first.
- Network edits: which edges, junctions, or stops were changed, and why (with IDs where known).
- Relevant commits (hash plus a one-line summary).

## 6. SUMO technical notes
SUMO version, the tools we use (netconvert, netedit, duarouter, randomTrips, gtfs2pt, etc.), required environment variables (SUMO_HOME), Python dependencies, and any quirks, errors, or fixes we found along the way.

## 7. Decisions and conventions
Design choices we made and the reasons for them, naming conventions, coordinate/projection settings, and anything I told you I prefer.

## 8. Open questions and known issues

Keep it dense and factual: bullet points, exact file paths, and exact commands. Where you're unsure about something, mark it **[UNVERIFIED]** rather than guessing. Aim to keep HANDOFF.md under about 9,000 characters (it gets injected into context automatically, and anything much longer is truncated to a preview). If you need more detail, move it into README or the working log and point to it.
