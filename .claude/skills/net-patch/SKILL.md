---
name: net-patch
description: Use when changing the SUMO street network - .net.xml edits, lanes, connections, turn restrictions, signals/tlLogic, bus lanes, pedestrian-only paths, spreadType/geometry, or patch files in Simulation/GTFS/additional_net/. Also when the network must be rebuilt or patches reapplied.
---
# Network patch workflow

Network: `Simulation/GTFS/soheil_seattle_merged.net.xml` (source) -> `soheil_seattle_merged_pedspeed.net.xml` (used by the GTFS configs, made by the ped-speed cell `a7d6fe60-...` in `GTFS/seattle_sumo_network_setup.ipynb`). Signals for the GTFS configs: `clean corrected inputs/correct_Alaskan_new_signal_additional_columbia_eb.add.xml` (programID 2 overrides the net's programs).

## Rules
- Never hand-edit either `.net.xml`. Every change is a reapplyable patch in `GTFS/additional_net/` (`.nod/.edg/.con/.tll.xml`); signal-file changes are a `.diff` with the apply command in its header. Unapplied ideas go in `additional_net/drafts/`.
- Build and test on a copy first (scratchpad). Apply to the real net only after the checks below and the user's OK.
- Don't break the older configs (`clean_reformed_Seattle.sumocfg`, `fullDayTests.sumocfg`): never edit shared files in place, copy them.
- Boundary edges that are TAZ sources/sinks keep their ids (e.g. `22759220#9`, Summit/Bellevue Ave E edges). Check `clean corrected inputs/forMFD_Taz_with_pseudo.add.xml` before renaming or splitting a boundary edge.
- Regenerating the whole network = destructive: ask first.

## Steps
1. Find ids: grep the net for the edge/junction/tls (never cat it). sumolib (`sumolib.net.readNet`) for geometry, connections, `getShortestPath(..., vClass="bus")`.
2. Write the patch. Existing edges keep stored connections when neighbours are added, so list turns from former dead ends explicitly in `.con.xml`; delete with `<delete from= to= fromLane= toLane=/>`.
3. Build on a copy, from `Simulation/GTFS/`:
   `netconvert -s <copy>.net.xml -e additional_net/X.edg.xml -x additional_net/X.con.xml [-n X.nod.xml] [-i X.tll.xml] --no-turnarounds -o <copy>.net.xml`
4. Check the copy:
   - Diff connections/tls link indices before vs after (script: count connections per touched junction, list changed ones). A removed connection shifts tls link indices: update the signal file programs to match (state string length = link count).
   - Bus paths: sumolib shortest bus path through the area; list GTFS lines whose routes used removed edges/connections (grep `GTFS/bus/gtfs_pt_vehicles.add.xml`).
   - Load check: short run (05:00-05:15, transit only) -> exit 0, no new warnings vs the 6 known errors. Override outputs to the scratchpad (see sim-analysis skill).
5. Before/after sim: transit-only locally if < 15 min; full run with cars goes to the lab (`lab-server_sumo`).
6. Apply: reapply on `soheil_seattle_merged.net.xml`, rerun the ped-speed cell (Windows setup cell first), apply any signal `.diff`.
7. Downstream (any change touching bus edges or stops): delete `GTFS/resources/` and `GTFS/input/`, rerun the GTFS notebook chain and riders (gtfs-pipeline skill), rerun `route_buses_by_shape.py`.
8. Document: reapply command + what/why in GTFS README "Network patches (`additional_net/`)", Work_Done.txt entry.

## Reference (grep, don't read whole)
- Patch table and full reapply order: `Simulation/GTFS/README.md`, section "Network patches (`additional_net/`)". Order: columbia_eb_bus -> mercer_st -> mercer_st_pass2 -> network_fixes -> e_union_st_wb_bus -> belmont_bellevue_pl -> third_yesler (+ signal diff) -> ped_only_paths -> ped-speed cell.
- Signal timing background and drafts: same README, "Known limitations" and "Drafts (not applied)".

## Pitfalls
- Git Bash mangles comma-separated `C:/` path lists: prefix `MSYS_NO_PATHCONV=1`.
- spreadType changes move lane geometry and can move snapped bus stops onto other edges (2026-10-23: re-centring gneE173 moved stop 1610 onto Yesler). Re-check stops after geometry edits.
- `sumo` doesn't create output folders.
- Signal/README/Work_Done files are CRLF: edit with Edit or Python, not `sed -i`.
