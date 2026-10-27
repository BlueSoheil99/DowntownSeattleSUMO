---
name: sim-analysis
description: Use when running a SUMO test, reading or comparing simulation outputs (tripinfo, log.xml, teleports, boardings, skipped stops, warnings), deciding if a change is a regression, or writing a run request/report for the lab server.
---
# Running and analysing simulations

## Never print raw output
Don't cat/grep-dump `tripinfo_output.xml`, `vehroute_output.xml`, `log.xml`, edge data. Summarise:
```
cd Simulation
python tools/summarize_run.py "<out_dir>"                       # one run
python tools/summarize_run.py "<new_dir>" --compare "<base_dir>" # A, B, A-B
python tools/summarize_run.py "<out_dir>" --json m.json          # for averaging seeds
python tools/summarize_run.py "<new>@<gtfsA>" --compare "<base>@<gtfsB>"  # each run with its own transit files
```
Needs `<dir>/tripinfo_output.xml` (or `tripinfo.xml`, or `--tripinfo NAME`) and `<dir>/log.xml`. Bus/rail lines from `<gtfs>/bus|rail/gtfs_pt_vehicles.add.xml` (default `GTFS/`). Boardings exclude `rider_in_*` (on board at entry) and `link_*` persons. Link expected = personFlow rates in the Link `.rou.xml` x overlap with `--window` (default 18000 43200). `--compare` also lists new warning/error types. Bus targets are 05:00-12:00, so ratios from short runs are low by design. Validated by the lab on S2/X1 (2026-10-27): every metric matches its reports. For a question the script doesn't answer, write a small streaming (`iterparse`) script that prints counts/means only.

## Running
- From `Simulation/`: `sumo -c gtfs_ridership_vehicular.sumocfg` (full) or `gtfs_transit_only.sumocfg`.
- Test runs must not write to `new output/` (the user may be running sumo-gui on the same config). Override outputs and the additional files that write outputs, e.g. `--tripinfo-output <scratch>/tripinfo_output.xml --vehroute-output "" --log <scratch>/log.xml` and pass `--additional-files` without the edge_data adds. Create the folder first (sumo won't).
- Short window: `-b 18000 -e 18900`.
- Over 15 min (anything 05:00-09:00 with cars, ~2 h here) -> lab server. Local only for short checks.
- Seeds: `--seed 2`, `--seed 3`. Car metrics need >= 3 seeds before calling an effect.

## Lab request (SendMessage to `lab-server_sumo`; ListAgents first)
```
Run <ID>: commit <sha> (git pull), config <file>, window <b>-<e>, seeds <list>.
Compare to <baseline ID>. Reply: headline + summarize_run.py --compare table, <= 30 lines.
Full detail in lab_notes/<ID>_report.md.
```
If the lab isn't listed, it's unreachable from this session (long sessions time out); tell the user.

## Baseline and what counts as a regression
Baseline **S2 (df4663c)**, 3 seeds (2026-10-26): car mean duration 415 s (408-420), car teleports ~1130 (1026-1250), bus teleports ~70, person teleports ~8, skipped stops ~9, bus boardings/ridership 0.975, lines >=100 riders within 10%: 30-33 of 33, Link finished 94.2%.
Flag: boardings < 0.95; lines within 10% < 30; bus teleports or skipped stops clearly above the seed range; new warning types; errors beyond the 6 known; any `right_before_left` hotspot (junction 53129291 watched); transit rerouted > 0.
Single-seed car differences under ~230 teleports / ~3% duration are noise.

## Notes
- Expected warnings: 3277 "Taz usage was requested" (transit), actuated-tls detector warnings, 6 known errors (linkMin/MaxDur).
- Skipped stops include trains (e.g. `751013565#1_0` is a Link stop). "Person ... cannot use waiting vehicle" is not counted as a person teleport.
- The lab's own deeper scripts (`lab_notes/scripts/` in the lab clone): `compare_runs.py` (per-line teleports/trip time by line group), `analyze_link.py` (Link waits, station boardings/alightings, train loads), `analyze_w.py` (teleports by hour/lane/reason, per-line boardings), `bus_tp_lanes.py` (bus teleports/skips by line and lane), `run_full.sh` (standard run + real exit code). Ask the lab for these instead of rewriting them.
- Lab clone: `C:\Users\dharoot\Documents\iUTS_Projects\DT_Seattle_SUMO_git`, notes in `lab_notes/` (index `README_LAB.md`).
