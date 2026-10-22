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
Keep this section under about 1,500 characters. The SessionStart hook prints only the file's title line and this section (the context preview cuts hook output at ~2 KB), so it must stand on its own. Put run commands and other detail in sections 3–6. In this order:
- **Now:** 3–5 lines: the current task, what we're waiting on (lab runs, replies, user decisions), and the very next step.
- **Sessions:** the primary home session's name (this session's; check with `ListAgents`), the lab session (`lab-server_sumo`) and what is outstanding with it. Rule: the lab replies to whichever session sent the request, so a new primary session messages the lab with its name, and the old session forwards anything that reaches it.
- **Uncommitted / pending:** local changes not yet committed, and questions I haven't answered yet.
- **Works:** one or two lines (what runs, the config to use).
- **Next steps:** 3–5 concrete steps, one line each.

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

Keep it dense and factual: bullet points, exact file paths, and exact commands. Where you're unsure about something, mark it **[UNVERIFIED]** rather than guessing. Aim to keep HANDOFF.md under about 9,000 characters (the new session reads the whole file itself). If you need more detail, move it into README or the working log and point to it. Before saving, check that nothing important lives only in this conversation or in a temporary scratchpad folder (test files, methods, environments); copy it into the repo or describe it, since scratchpads disappear with the session.
