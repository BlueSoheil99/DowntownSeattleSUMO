---
name: gtfs-pipeline
description: Use when generating or changing transit inputs - GTFS feeds, the seattle_sumo_gtfsData_setup notebook, gtfs2pt, bus/rail stops and routes, vehicle types, stop lengths, bus or Link riders (ridership_personflows.py, rail_personflows.py), scenario.json, or regenerating transit files after a network change.
---
# GTFS transit pipeline

Everything runs from `Simulation/GTFS/` (notebook) or `Simulation/ridership/` (riders). Settings: `Simulation/scenario.json` (bus feed, sim date, ridership period, lines, `rail` section; `SUMO_SCENARIO` env picks another file).
Current inputs: bus `gtfs data/kcm_google_transit_FAL25.zip` (fall 2025, ridership period 253); rail `rail_gtfs.zip` with weekday 2026-04-22 (spring 2026 Link boardings). Schedule and ridership must come from the same period.

## Notebook order (`seattle_sumo_gtfsData_setup.ipynb`; restart kernel first)
Cell ids in brackets (stable; positions shift).
1. Setup `5aeac350` (Windows; never the Mac cell on Windows). Overrides PATH/PYTHONPATH; anaconda must be first on PATH or `!python` gtfs2pt fails on `rtree`.
2. Load `6825a4dc` -> bus filter `d51c3c06` (writes `gtfs data/kcm_google_transit_downtown.zip`)
3. Stop snapping `14157d2a` (rewrites the filtered zip in place: always rerun the filter first)
4. Rail filter `fdc0ae87` -> rail gtfs2pt `d0a8958f`
5. Bus gtfs2pt `7be7ec6c` (`--original-lines --use-gtfs-stopids --patched-stops bus/patched_stops.add.xml`)
6. Shape routing `5b1e7c2a` (`route_buses_by_shape.py`, MIN_GAIN 150 m)
7. Link vTypes `cf9bfc97`, then bus vTypes `68b27bce` (types from `vtype_by_line.csv`; stop lengths 20/40/60 m bus by peak buses/h, 120 m rail). Edit the cells, never `bus.add.xml`/`tram.add.xml`.
Headless runs: execute these cells by id with IPython, anaconda first on PATH.

## After any network change
Delete `GTFS/resources/` (gtfs2pt cache, keyed by net path; stale after net changes), `GTFS/input/` and `fcd/`, rerun the chain above, then riders:
```
cd Simulation/ridership
python ridership_personflows.py      # -> kcm_riders_253_AM_MID.rou.xml (+ _summary/_skipped.csv)
python rail_personflows.py           # -> link_riders_2026-04_05_AM_MID.rou.xml
```
Then check: `python GTFS/check_bus_routes_vs_shapes.py` (needs shapely+pyproj venv; see README "Route check") -> expect 0 real deviations, ~198 Alaskan Way artifacts; and a transit-only 05:00-12:00 run (~local OK) compared with `tools/summarize_run.py`.
Expected counts (2026-10-23): 4466 buses, 230 stops, 531 trains, 6224 bus personFlows, 836 Link flows. Report any change.

## Generated files committed (reference set)
`bus/` and `rail/` `gtfs_pt_vehicles.add.xml`, `gtfs_pt_stops.add.xml`, `bus.add.xml`/`tram.add.xml`, `vtypes.xml`, the downtown zips, both rider `.rou.xml`. Regenerate and commit them together with the change that caused it. CSVs go to LFS; summary/skipped CSVs are not committed.

## Pitfalls
- SUMO 1.28.0+ required (duplicate stop ids #18237, stale cache #18291).
- `--original-lines` keeps line names plain; without it lines become `D_Line#1` and riders only board the first variant.
- Lines not in `vtype_by_line.csv` keep the default type with a warning.
- Stop snapping rules (35 m, 45 deg, 7 m from edge ends, dropped stops) and the line review history: GTFS README sections "Bus stop snapping" and "Reviewed bus lines".
- Buses hold at every stop until scheduled time (gtfs2pt `until`); timepoint-only holding untested.
- Mac setup cell still points at 1.27.1 [UNVERIFIED on 1.28].

## Reference (grep these headings in `Simulation/GTFS/README.md`)
"Bus schedule and ridership: same service period", "Scenario file", "Link riders", "Route check vs GTFS shapes", "Bus routes along the GTFS shapes", "Bus and train types, stop lengths", "Generated transit files in git".
