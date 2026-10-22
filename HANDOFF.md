# HANDOFF: Downtown Seattle SUMO digital twin (2026-10-22)
Repo `BlueSoheil99/DowntownSeattleSUMO`, branch `main`, HEAD `fe0d81f` = origin. Details: `Simulation/GTFS/README.md` (main technical doc), `Simulation/ridership/readme.md`, dated log `Simulation/Work_Done.txt`.

## 1. Role
You are a lab/research assistant helping build a digital twin of downtown Seattle in SUMO with multiple transit modes. Your responsibilities:
- Write and maintain Python scripts for importing maps (OSM), travel demand, ridership, GTFS bus routes/stops, and other inputs.
- Edit .net.xml and related network files so the street network matches real life (lanes, turn restrictions, signals, bus lanes, stops).
- Give technical feedback, and explain any pipeline in the project in detail when asked.
- Keep the working log and README files up to date as changes are made.
- Ask before making destructive changes (deleting files, regenerating the network, force-pushing).
Rules in `CLAUDE.md` (commits: list files + get OK, stage by name; test sims never write to `Simulation/new output/`).

## 2. Project status snapshot
**Works:** cars (PSRC 2018 TAZ demand, ~206k trips) + 40 KCM bus lines + Link 1/2 Line + bus riders + Link riders, 05:00-12:00, step 0.1 s.
- Run from `Simulation/`: `sumo -c gtfs_ridership_vehicular.sumocfg` (full) or `sumo -c gtfs_transit_only.sumocfg` (no cars/riders). GUI: `& "C:\Program Files (x86)\SUMO\bin\sumo-gui.exe" -c ...` (PowerShell). Full run ~2 h on the lab server, single-threaded.
- Bus boardings 0.97 x ridership (31/33 big lines within 10%); bus routes 94% on the GTFS shape.
**Lab server:** session `lab-server_sumo` (Remote Control; `ListAgents` then `SendMessage`), git clone `C:\Users\dharoot\Documents\iUTS_Projects\DT_Seattle_SUMO_git` at fe0d81f; its notes in `lab_notes/`. Use it for long runs.
**Most recent work:** Link riders (fe0d81f); rail modularity test on the lab (5 Link periods 2022-2025 all ran; 2 needed one-line fixes); W2 full run with Link riders running on the lab, results pending.
**Next steps:**
1. Collect W2 results from the lab (Link rides, train loads, bus/car changes vs W_vtypes).
2. Robustness fixes from both modularity tests (Work_Done Oct 22): stop when the filter keeps 0 lines; normalise line names ("1-Line"); `load_gtfs` skip unparseable files + `dtype=str`; write only standard GTFS columns in both filter cells; station alias table in `rail_personflows.py`; check sim date has trips per line. Test on a copy.
3. 3rd Ave & James St bus hotspot: signals `53221905`/`764028198` to 90 s (tested on copy: teleports 101->71), hold buses only at GTFS timepoints (untested).
4. Shape-based bus routing after gtfs2pt (108 trips off-shape, 4 places).
5. Report draft for the research write-up.

## 3. Repo structure (Simulation/)
- `scenario.json` + `scenario.py` (H): scenario settings (bus feed, sim date, ridership period, lines; `rail` section). `SUMO_SCENARIO` env selects another file.
- `gtfs_ridership_vehicular.sumocfg`, `gtfs_transit_only.sumocfg` (H): GTFS configs. `clean_reformed_Seattle.sumocfg`, `fullDayTests.sumocfg`: older car-only configs, don't break.
- `adjusted_alaskanway_..._V3.rou.xml` (G, Soheil's demand notebooks): car demand. `Demand generation/`: those notebooks.
- `clean corrected inputs/`: TAZs (`forMFD_Taz_with_pseudo.add.xml`), signals (`correct_Alaskan_new_signal_additional_columbia_eb.add.xml` used by GTFS configs).
- `GTFS/seattle_sumo_gtfsData_setup.ipynb` (H): GTFS pipeline. `GTFS/seattle_sumo_network_setup.ipynb`: network + ped-speed cell.
- `GTFS/soheil_seattle_merged_pedspeed.net.xml` (G): the network. `GTFS/additional_net/`: network patches.
- `GTFS/gtfs data/`: `kcm_google_transit_FAL25.zip` (bus, in use), `_SPR26.zip` (old), `rail_gtfs.zip`, `*_downtown.zip` (G).
- `GTFS/bus/`, `GTFS/rail/` (G by notebook, committed as reference set): `gtfs_pt_vehicles/stops.add.xml`, `bus.add.xml`, `tram.add.xml`.
- `GTFS/vtype_by_line.csv` (H, LFS): line -> vehicle type/color. `GTFS/check_bus_routes_vs_shapes.py` (H): route check -> `route_check/` (G).
- `ridership/ridership_personflows.py` -> `kcm_riders_253_AM_MID.rou.xml`; `ridership/rail_personflows.py` -> `link_riders_2026-04_05_AM_MID.rou.xml` (both committed). Data: `ridership/data/routeData/kcm/` (LFS), `ridership/data/link/` (LFS).
- `sumo_issue_drafts/` (untracked): GitHub issue texts.

## 4. Pipelines (details in GTFS README)
- **Network:** OSM -> netconvert -> Soheil netedit -> merged with Zili's rail -> 6 patches (reapply commands in README) -> ped-speed cell. After a change: delete `GTFS/resources/`, rerun GTFS cells + riders.
- **Car demand:** PSRC 2018 -> TAZ trips (fromTaz only; `device.rerouting.with-taz`). Not touched.
- **GTFS (notebook, from `GTFS/`, restart kernel):** setup cell (Windows `5aeac350`; never the Mac cell on Windows) -> load_gtfs -> bus filter -> stop snapping -> rail filter -> rail gtfs2pt -> bus gtfs2pt (`--original-lines --use-gtfs-stopids`) -> Link vType cell -> bus vType cell (types per line, stop lengths 20/40/60 m bus, 120 m rail).
- **Riders:** from `ridership/`: `python ridership_personflows.py`, `python rail_personflows.py`.
- **Check:** `GTFS/check_bus_routes_vs_shapes.py` (needs shapely, pyproj).

## 5. Change history (newest first; full log in Work_Done.txt)
- `fe0d81f` Link riders, weekday rail date 2026-04-22, rail scenario section, `--original-lines` for rail.
- `1d75d16` scenario.json/scenario.py; coverage and missing-line warnings.
- `30b4bbc` bus schedule -> KCM FAL25 (2025-10-15), matching ridership period 253.
- `f4e03d9` generated transit files committed as reference set.
- `bdd4f1a` vehicle types by line (40/60 ft, trolley, RapidRide, Link 2-4 car), stop lengths, route check.
- `33ce63f` `device.rerouting.pre-period 0` (crash fix, SUMO bug, reported as eclipse-sumo/sumo#18408).
- `28e1f84` bus riders; single-threaded. `6ee46ab`, `a3337d4`, `358818f`: line reviews; network patches (Columbia EB bus lane, Mercer St, E Union St, Belmont/Bellevue Pl, connection fixes).

## 6. SUMO technical notes
- SUMO 1.28.0, `C:\Program Files (x86)\SUMO` (SUMO_HOME). Lab: same. Mac **[UNVERIFIED]**.
- Python: home `C:\Users\dahh2\anaconda3\python.exe` (pandas, rtree; gtfs2pt needs rtree on PATH). Don't pip-install sumolib/traci. Route check needs shapely+pyproj (not in anaconda).
- Keep `pre-period 0` in configs (else segfault ~07:13-08:11). Multithreading with riders crashes: `threads 1`.
- Git Bash mangles comma-separated `C:/` path lists: `MSYS_NO_PATHCONV=1`. SUMO doesn't create output folders.
- `*.csv` goes to Git LFS (`.gitattributes`). Work_Done.txt and READMEs are CRLF.

## 7. Decisions and conventions
- Update a schedule and its ridership together (same period). Bus = fall 2025, rail = spring 2026 (2 Line downtown only since 2026-03-28).
- TAZ demand stays. Step 0.1 s. Network edits only as patch files, tested on a copy.
- Link alightings = boardings, time of day from KCM buses: assumptions, marked TO REVISIT.
- No SUMO contributions/CLA for now (user, 2026-10-22).
- User: dense factual answers, mark unknowns [UNVERIFIED], works on Windows and Mac.

## 8. Open questions and known issues
- Signal timing source undocumented (ask Soheil / SDOT records request).
- Buses appear/disappear at trip ends; riders only at stops; through Link riders not generated.
- W99 car-following params ignored (Krauss runs).
- Marymoor Village has no trainStop; terminus layover boarding issue (Northgate/Angle Lake in older feeds).
- Lab's 2025-04 Link boardings look off (Northgate 3,503, Stadium 6,804).
- GitHub: #18341 (bug, open), #18342 (feature, open), #18408 (crash, open).
