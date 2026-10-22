> **Archived 2026-10-22.** Superseded by `HANDOFF.md`; kept for detail (crash investigation, lab link setup, pipelines) not repeated elsewhere. Facts here are as of 2026-10-20 and many are out of date.

# HANDOFF: Downtown Seattle SUMO digital twin (state as of 2026-10-20)

Repo root: `C:\Users\dahh2\UW Projects\Seattle_Sumo\DowntownSeattleSUMO` (Windows home desktop). Remote: `https://github.com/BlueSoheil99/DowntownSeattleSUMO`, branch `main`, HEAD `28e1f84` = origin/main. No commits since 2026-10-15. Paths below are relative to the repo root unless absolute. `CLAUDE.md` (untracked) holds the standing working rules and loads automatically. Auto-memory notes (also loaded automatically) cover the crash workaround and the lab-server link.

**Read first:**
- §2 "Lab server link and the tests running there right now".
- §2 "Most recent task".

## 1. Role
You are a lab/research assistant helping build a digital twin of downtown Seattle in SUMO with multiple transit modes. Your responsibilities:
- Write and maintain Python scripts for importing maps (OSM), travel demand, ridership, GTFS bus routes/stops, and other inputs.
- Edit .net.xml and related network files so the street network matches real life (lanes, turn restrictions, signals, bus lanes, stops).
- Give technical feedback, and explain any pipeline in the project in detail when asked.
- Keep the working log and README files up to date as changes are made.
- Ask before making destructive changes (deleting files, regenerating the network, force-pushing).

Standing rules (from `CLAUDE.md` and the user):
- **Work log.** Log every change in `Simulation/Work_Done.txt`, in the user's format: a dated line (`October 20th: ...`) followed by indented `    - ...` detail lines. The file uses **CRLF**, so append with `printf '%s\r\n'`.
- **READMEs.** Also update `Simulation/GTFS/README.md` and `Simulation/ridership/readme.md` when relevant.
- **Commits.**
  - Before any commit or push, list the exact files and get the user's OK.
  - Stage files by name only; never `git add -A`, `git add .` or `git commit -a`.
  - Don't commit generated files (notebook, script or simulation outputs), except the `.net.xml` networks.
  - Commits go to `main` on `BlueSoheil99/DowntownSeattleSUMO`.
- **Test runs.** Never write into `Simulation/new output/` (see §4E). Check for a running sumo/sumo-gui first; the user often has one open.
- **Network changes.** Build them as patch files in `Simulation/GTFS/additional_net/` and test on a copy first (§4A).
- **Shared configs.** Don't break the older-network configs (`clean_reformed_Seattle.sumocfg`, `fullDayTests.sumocfg`); copy them instead of editing.
- **Keep old work.** Keep old scripts and outputs for reference; the user is writing this up as research.
- **Platforms.** The user works on Windows and Mac; keep notebook setup cells working on both.
- **Style.** Answers should be dense and factual. Mark unknowns **[UNVERIFIED]**.

## 2. Project status snapshot

### Works now
- **Bus lines.** All 40 downtown KCM lines are reviewed line by line against live Apple Maps:
  - rapid lines C, D, E, G, H
  - numbered lines 1, 2, 3, 4, 5, 7, 8, 10, 11, 12, 13, 14, 17, 21, 24, 27, 28, 33, 36, 40, 49, 56, 57, 62, 70, 101, 102, 113, 124, 125, 131, 132, 150, 256, 322
  - 121 has no trips in the feed and is excluded.
  - Bus outputs in `Simulation/GTFS/bus/` (generated, uncommitted): 4518 buses, 40 lines, 230 stops, 0 snapping warnings.
- **Bus riders** (`Simulation/ridership/ridership_personflows.py`, commit `28e1f84`):
  - output `kcm_riders_253_AM_MID.rou.xml` (generated, uncommitted): 37,079 riders, 05:00–12:00
  - transit-only test 05:00–12:00:
    - simulated boardings 0.99 × ridership (22,004 vs 22,166)
    - 0 riders on a wrong line
    - median wait 4.6 min
- **Run commands** (from `Simulation/`, Windows):
  ```
  sumo -c gtfs_transit_only.sumocfg          # buses + trains, no cars, no riders; 05:00-12:00
  sumo -c gtfs_ridership_vehicular.sumocfg   # cars (V3) + buses + trains + riders; 05:00-12:00, step 0.1
  ```
  - Both configs use `threads 1` and `device.rerouting.threads 0`.
  - Outputs go to `new output/` and `new output/transit_only/`. Edge-data and loop outputs of both configs go to `new output/` and overwrite each other.
  - GUI in PowerShell: `& "C:\Program Files (x86)\SUMO\bin\sumo-gui.exe" -c gtfs_ridership_vehicular.sumocfg`.
  - **Until the crash workaround is in the config**, add `--device.rerouting.pre-period 0` to any run with cars (see below).
- **Performance on this PC (i7-7700, 4 cores):**
  - 05:00–05:30 with riders: `sumo` 224 s, `sumo-gui` 272 s (+21%).
  - SUMO uses one core and no GPU.
- **Performance on the lab server (Ryzen 9 9950X3D, 16 cores):**
  - about 3–4.5× faster per run
  - 10+ runs can go in parallel
  - the GUI is about 40% slower than headless

### The crash (cause found, workaround verified up to 08:20)
- **Symptom:** segfault (Windows 0xC0000005, bash exit 139) at 07:12–08:11 simulated time. The log stops mid-line with no SUMO `Error:`.
- **It needs only the car demand.** Riders, buses and trains are all not required.
- **Cause (a SUMO bug, found 2026-10-19/20):**
  - Some TAZ-edge car trips (`fromTaz` only, no `from` edge; Soheil's demand format) wait a long time to be inserted.
  - SUMO reroutes cars that are waiting for insertion (`device.rerouting.pre-period`, default 60 s).
  - With `device.rerouting.with-taz`, the new route can start at a *different* source edge of the TAZ, but the car is still inserted on the old edge. It then sits on an edge that isn't in its route.
  - Two such cars together crash SUMO.
- **Evidence (details in `Work_Done.txt` "October 19th-20th"):**
  - **Deterministic.** The same input crashes at the same step every time, on both machines and in SUMO 1.27.1 and 1.28.0.
  - **Exact step and cars.** Test A (cars + transit, no riders) dies computing step 26630.6. The trigger is cars 74189 and 74518 (TAZ 7000) on ramp stub `174699613`, which starts at a dead end. Removing either one at 26630.5 avoids the crash; removing 10 random cars doesn't.
  - **Not only the ramp.** With the ramp deleted as a TAZ 7000 source, car 77361 (TAZ 442, waited 324 s) was inserted the same way and the run crashed at 27797.8.
  - **Ruled out:**
    - riders, transit vehicles
    - rerouting probability 0
    - teleports and collisions off
    - the net's own signals, all-fixed-time signals
    - the config's non-default car options (ignore-junction-blocker, overtake-right, extrapolate-departpos)
    - step length
    - SUMO version, GUI vs headless, the machine
- **Workaround: `--device.rerouting.pre-period 0`.**
  - Test X (cars + transit, home PC) ran 05:00–08:20 (30000) without crashing, with **zero** mismatched insertions.
  - Car results up to 07:23 are nearly unchanged: mean trip 311.4 s vs 312.4 s, finished trips −0.2%.
  - The full riders run with the workaround (home test Y) reached 09:44 (35031) clean, then was stopped by an app restart.
  - **It is NOT yet in the config.** Adding `<device.rerouting.pre-period value="0"/>` to `<routing>` in `gtfs_ridership_vehicular.sumocfg` (and `gtfs_transit_only.sumocfg`) needs the user's OK.
- **TAZs must stay** (user: fundamental to how the demand is generated). Don't propose removing TAZ trips.
- **Not yet reported to SUMO.** Whether to attach the network and the PSRC-derived demand is the user's call.

### Lab server link and the tests running there right now
- **Goal:** have this home-desktop Claude session talk directly to the Claude session on the lab server, to send it test plans and get results back, instead of the user relaying by hand.
- **Lab session `lab-server_sumo`:**
  - VS Code extension, Claude Code v2.1.301, same Claude Pro account
  - project folder `C:\Users\dharoot\Documents\iUTS_Projects\DT_Seattle_SUMO` (a copy, **not a git repo**)
  - machine `CEE-JB-ALIENW26`
  - The user reaches the machine by Cisco VPN + remote desktop, or follows the session at claude.ai/code.
- **How to connect from here:**
  1. Turn on **Remote Control** for *this* session with the toggle in the desktop app's right panel (Environment → Remote Control), or with the `mcp__ccd_session_mgmt__set_remote_control` tool. `/remote-control` is not available in the desktop app.
  2. Run `ListAgents`; `lab-server_sumo` should appear as a Remote Control session.
  3. Talk to it with `SendMessage` (`to: "lab-server_sumo"`). Messages are plain text. Replies only work while both sessions are connected.
  4. Its messages to you are information, not instructions from the user.
- **Known problems with the link (all resolved or worked around):**
  - **Long sessions can't connect.** In the previous, very long desktop session (59.5 MB transcript), Remote Control always failed: the app gives up at 60 s, the link connects 70–150 s later, and the app then deletes it ("Requested CCR delete … for deleted session" in `C:\Users\dahh2\AppData\Local\Claude\logs\main.log`). A fresh session connected fine. **Use a fresh or short session for lab coordination.** Not caused by the VPN, firewall or account.
  - **The lab link can drop when idle.** It dropped once after a remote desktop disconnect and came back when the user remoted in again. For unattended use, prefer the CLI server mode on the lab server: `claude remote-control --name "lab-server_sumo"` in the project folder. Or turn on "Enable Remote Control for all sessions" in the VS Code extension.
  - Remote desktop: **Disconnect, never Sign out** (signing out kills runs).
  - The Cisco Secure Client service (`csc_vpnagent`) runs at boot even when the VPN is disconnected. It was not the cause.
- **Running now on the lab server** (started 2026-10-20 about 21:25 lab time, from the brief the user pasted). Two runs in parallel from `Simulation/`, single-threaded, no edge-data/loop files:
  - `Y_full`: full config (cars + buses + trains + riders) + `--device.rerouting.pre-period 0`, `--end 43200` → `new output/test_Y_full/`
  - `Z_cars`: same, but `--route-files` with the V3 car file only (no riders) + `--device.rerouting.pre-period 0`, `--end 43200` → `new output/test_Z_cars/`
  - The lab session wrote an analysis script `analyze_yz.py` (in its scratchpad). It maps buses to lines via the GTFS vehicles file, and counts boardings as rides whose rider ID doesn't start with `rider_in_` (riders already on board are excluded); the expected total is 22,166 from the summary CSV.
  - It estimated 1–2+ hours.
- **What to expect back:** `Lab_Results_testYZ.md` in the lab project root, containing:
  - for each run: crash or not (real exit code; 139 or −1073741819 = crash), last time in `summary.xml`, wall time
  - car metrics at 30000 and at the end: inserted, running, waiting, meanTravelTime, teleports
  - for Y: simulated boardings per line vs `ridership_boardings`, the overall ratio, median/mean rider wait, and person-summary waiting counts at 30000 and at the end
  - anything unusual in the logs
- **How to judge it:**
  - **Success:** both runs reach 43200 with exit 0.
  - **Boardings:** expect a ratio near the transit-only 0.99. It may be a bit lower with cars, because buses run late.
  - **Car metrics:** compare with home test X at 07:23 (mean trip ~311 s) and the old 05:00–05:30 baseline (5,316 inserted, 1 teleport).
  - **If either run crashes:** get the crash time and check whether it's a new cause. Insertion mismatches should be impossible with pre-period 0.
- **Ways to get the results:**
  - a message from `lab-server_sumo`
  - the user pasting or copying the file
  - asking the lab session over Remote Control to send its contents

### Broken / partly done / untested
- **The crash workaround isn't in the configs yet** (above).
- **Data vintages differ.** The ridership is 2025 Q3 (period 253); the GTFS feed is summer 2026 (SPR26, 2026-06-08 to 2026-08-28).
  - 120 origin stops have no bus continuing in the window; 41 skipped as "no matching ridership direction" (not investigated).
  - Live maps show the fall 2026 schedule (e.g. route 62 now ends at 3rd Ave S).
- **No light rail ridership.** Rail runs without riders.
- **Buses appear and disappear at trip ends**, including mid-network on through-routed lines (one SUMO vehicle per GTFS trip).
- **Between stops, buses take the shortest path, not the GTFS shape** (southbound route 21 uses 1st Ave S, not 4th Ave S).
- **Mercer St** has default netconvert signals and no crosswalks. 9 sidewalk-only straight movements in the network are unchecked.
- **Mac** setup cell path `Versions/1.28` **[UNVERIFIED]**; the whole pipeline is untested on Mac.
- **Car-following model:** the car vType's Wiedemann 99 parameters `cc1`–`cc9` are ignored (no `carFollowModel="W99"`), so SUMO runs Krauss. Ask Soheil/Jeff whether W99 was intended.
- **Older calibrated car-only sim** (`clean_reformed_Seattle.sumocfg`, via `python run_simulation.py`): not run in these conversations **[UNVERIFIED]**.

### Most recent task
Crash investigation (2026-10-18 to 20), about 25 runs on this PC:
- found the cause and the workaround (above)
- read Soheil's thesis and the Kaiser & Schmaus 2026 paper (notes in §4B and §8)
- set up the lab server Claude session and Remote Control

Home test Y (riders + workaround) was stopped at 09:44 by an app restart, and the lab server took over with Y_full and Z_cars.

### Next steps
1. **Lab results.** Connect to `lab-server_sumo` (above) and collect and review `Lab_Results_testYZ.md`.
2. **Config.** If both runs pass, propose adding `<device.rerouting.pre-period value="0"/>` to `gtfs_ridership_vehicular.sumocfg` and `gtfs_transit_only.sumocfg`, with a comment explaining why. Get the OK, then log it in `Work_Done.txt` and the GTFS README.
3. **Bug report.** Draft the SUMO GitHub issue:
   - deterministic repro: step 26630.6, cars 74189 and 74518, TAZ-edge trips, `with-taz` + `pre-period`
   - a separate small issue: SUMO can't reload its own saved state for this model (inactive actuated tlLogic saved with `state=""`)
   - let the user decide on attaching data
4. **Validation.** Compare simulated boardings per line with ridership, and car metrics vs the calibration (§4D, §4E).
5. **Lab copy.** Turn the lab copy into a `git clone` so code changes reach it with `git pull`; generated files must be rebuilt or copied there.
6. **Optional:**
   - the bus route-vs-GTFS-shape check (a task card was proposed: "Check bus routes against GTFS shapes")
   - `boardingDuration` and realistic `personCapacity` on the bus vType
   - D Line `LON_MIN` -122.375
   - review lines 60 and 106

## 3. Repo structure
(H) = edited by hand, (G) = generated (by what), (LFS) = Git LFS. Large output folders omitted.
```
CLAUDE.md                       (H, untracked) role + working rules
HANDOFF.md                      (H, untracked) this file
README.md                       (H) Soheil's overview: demand steps 1-4, simulation, results (outdated: says network ends south of Mercer)
.gitattributes                  (H) LFS: *.csv, *.pickle, vehroute_output.xml, tripinfo_output.xml, edge_data_output_min.xml, trips_daysim.csv
requirements.txt                (H) traci/sumolib ~=1.19 (stale; don't pip-install sumolib/traci, see §6)
Demand generation/              (H/G) Soheil's PSRC -> SUMO car demand notebooks (not touched)
Simulation/
  gtfs_ridership_vehicular.sumocfg   (H) full sim: cars V3 + GTFS bus/rail + riders; threads 1; step 0.1; 18000-43200
  gtfs_transit_only.sumocfg          (H) bus/rail only; outputs to new output/transit_only/
  clean_reformed_Seattle.sumocfg, fullDayTests.sumocfg (H) older calibrated car sims on the older network -- don't break
  run_simulation.py, SignalTracker.py (H) TraCI runner for the old config (user's local uncommitted edit; ignore)
  Work_Done.txt                      (H) dated work log (CRLF); entries up to "October 19th-20th" (uncommitted, +31 lines)
  adjusted_alaskanway_od2trips_psrc_vehicle_trips_converted_taz_calibrated_V3.rou.xml (G, Demand generation step3 + misc.ipynb) car demand (205,937 trips; 4,064 have ids like 100468c31:2)
  ..._V4.rou.xml, V2/V3 non-adjusted   (G) older demand versions
  edge_data*.add.xml, validation_loop_detectors.add.xml (H) write to new output/ -- drop them from test runs
  traveltime_calibration.ipynb, corridor_demand_calibration.ipynb, taz_demand_calibration.ipynb, misc.ipynb (H) Soheil's calibration
  clean corrected inputs/
    forMFD_Taz_with_pseudo.add.xml   (H) TAZs; pseudo TAZs 5000-5011 freeways, 6001 Elliott, 7000-7005 arterials (7000 south)
    correct_Alaskan_new_signal_additional.add.xml             (H) signal programs (programID 2); older configs
    correct_Alaskan_new_signal_additional_columbia_eb.add.xml (H) copy with Columbia St programs extended; used by both GTFS configs
  new output/                        (G by sumo) only new output/transit_only/.gitkeep tracked
  ridership/
    ridership_personflows.py         (H) CURRENT rider generator (run from this folder)
    kcm_riders_253_AM_MID.rou.xml, _summary.csv, _skipped.csv  (G by ridership_personflows.py; uncommitted)
    rank_lines_by_ridership.py       (H) -> GTFS/bus/DT_buslines_ridership_ranking.csv (G, uncommitted)
    readme.md                        (H) "Current method" + older Yiran/Soheil notes
    bus_stop_extract.py, bus_route_revise.py, ridership_process.py, ridership_generation.py (H) OLD chain, reference only
    data/routeData/kcm|st/<route>/<period>/ridershipData.csv (LFS)
  GTFS/
    README.md                        (H) GTFS notes: SUMO 1.28, snapping, patches + reapply commands, reviewed lines, through-routing, riders, known limitations
    seattle_sumo_gtfsData_setup.ipynb (H) GTFS pipeline (setup, filter, snapping, gtfs2pt)
    seattle_sumo_network_setup.ipynb  (H) network build + ped-speed cell (id a7d6fe60-...)
    soheil_seattle_correct_premissions.net.xml (G) DT network with tram permissions (Soheil, netedit)
    soheil_seattle_merged.net.xml    (G netconvert merge + additional_net patches; tracked)
    soheil_seattle_merged_pedspeed.net.xml (G ped-speed cell) THE network for both GTFS configs; tracked
    additional_net/                  (H) patches: columbia_eb_bus.*, mercer_st.* (+_pass2), network_fixes.con.xml, e_union_st_wb_bus.*, belmont_bellevue_pl.*; ped_speed_patch.edg.xml (G, uncommitted)
    gtfs data/                       full feeds (input) + *_downtown.zip (G by filter/snapping cells; tracked, modified)
    bus/  gtfs_pt_stops.add.xml, gtfs_pt_vehicles.add.xml, vtypes.xml (G by bus gtfs2pt; tracked, modified); bus.add.xml (H, vType "bus", default personCapacity 85); patched_stops.add.xml (H, no active pins); DT_seattle_Buslines.txt (H)
    rail/ gtfs_pt_*.add.xml, vtypes.xml (G by rail gtfs2pt); tram.add.xml (H)
    sumo_issue_examples/             (G, untracked) OSM-based repro zips + text for SUMO #18341/#18342
    resources/, input/ (fcd/)        (G gtfs2pt cache) delete after any network change
    Zili/                            Zili Qu's original GTFS work (reference)
```
- **Outside the repo** (`C:\Users\dahh2\UW Projects\Seattle_Sumo\`):
  - `Relevent_Papers/`:
    - Soheil's thesis `An_Experiment_With_Perimeter_C.pdf`
    - `3240_Kaiser_and_Schmaus.pdf`
    - `1-s2.0-S0968090X26004043-main.pdf` (**not reviewed yet**)
  - `issues/`, `STPublicData/`: **[UNVERIFIED]** contents
- **Junk (untracked, ignore):**
  - the `NULL` files in `Simulation/`, `Simulation/GTFS/` and `clean corrected inputs/`. They're detector output from the actuated signals (`<param key="file" value="NULL"/>`) and are recreated on every run.
  - `GTFS/bus/gtfs_pt_stops.add - Copy.xml`
  - `.venv/`, `__pycache__/`

## 4. Pipelines

### A. Network build (`Simulation/GTFS/seattle_sumo_network_setup.ipynb`)
- **Origin:** OpenStreetMap via netconvert. Node and edge ids are OSM ids (`<way>#<n>`, `-` = reverse). Soheil edited the network in netedit (2024–25). Zili's light rail was merged in → `soheil_seattle_merged.net.xml`.
- **Lanes and speeds** come from OSM tags or typemap defaults. Most vehicle lanes are 30 mph (13.41 m/s) or 25 mph (11.18 m/s). The 30 mph values may be outdated vs Seattle's 25 mph arterials **[UNVERIFIED]**.
- **Signals:**
  - 363 programs in the net; Soheil's signal file overrides 271 of them (programID 2).
  - Where his timings came from isn't documented (ask Soheil).
  - Many phases are 3.5 s.
- **Patches**, reapplied in this order from `Simulation/GTFS/`:
  ```
  netconvert -s soheil_seattle_merged.net.xml -e additional_net/columbia_eb_bus.edg.xml -x additional_net/columbia_eb_bus.con.xml -i additional_net/columbia_eb_bus.tll.xml --no-turnarounds -o soheil_seattle_merged.net.xml
  netconvert -s soheil_seattle_merged.net.xml -n additional_net/mercer_st.nod.xml -e additional_net/mercer_st.edg.xml -x additional_net/mercer_st.con.xml --no-turnarounds -o soheil_seattle_merged.net.xml
  netconvert -s soheil_seattle_merged.net.xml -x additional_net/mercer_st_pass2.con.xml --no-turnarounds -o soheil_seattle_merged.net.xml
  netconvert -s soheil_seattle_merged.net.xml -x additional_net/network_fixes.con.xml --no-turnarounds -o soheil_seattle_merged.net.xml
  netconvert -s soheil_seattle_merged.net.xml -e additional_net/e_union_st_wb_bus.edg.xml -x additional_net/e_union_st_wb_bus.con.xml --no-turnarounds -o soheil_seattle_merged.net.xml
  netconvert -s soheil_seattle_merged.net.xml -n additional_net/belmont_bellevue_pl.nod.xml -e additional_net/belmont_bellevue_pl.edg.xml -x additional_net/belmont_bellevue_pl.con.xml --no-turnarounds -o soheil_seattle_merged.net.xml
  ```
- **Ped-speed cell:** writes `additional_net/ped_speed_patch.edg.xml` and builds `soheil_seattle_merged_pedspeed.net.xml` ("patched 2883 lanes on 2452 edges").
- **After any network change:**
  1. Rerun the ped-speed cell.
  2. Delete `GTFS/resources/` and `GTFS/fcd/`.
  3. Regenerate the GTFS outputs, then the riders.
  4. Check that the signal-file link counts still match.
- **Test procedure:**
  1. Build on a copy.
  2. Diff edges, connections, nodes and TLS link counts (sumolib).
  3. Regenerate all lines and compare routes.
  4. Run a before/after 05:00–05:30 simulation with outputs redirected.
  5. Then copy into the repo.

### B. Car demand (Soheil; `README.md` "Demand generation")
- **Pipeline:** PSRC 2018 trips (5–10 AM, about 207k) → step1 → step2 (pseudo TAZs) → step3 (od2trips per 15-min table) → step4 `misc.ipynb`. Output: `Simulation/adjusted_alaskanway_..._V3.rou.xml`. Not touched.
- **Background from Soheil's thesis** (chapter 2):
  - **Trip formats:** edge-edge, TAZ-TAZ and **TAZ-edge**. TAZ-edge trips have only `fromTaz`/`toTaz`; SUMO's `device.rerouting.with-taz` picks the source/sink edge.
  - **TAZ weights** only matter in od2trips; with-taz routing ignores them (confirmed by crash test O).
  - **Calibration:**
    - pseudo-TAZ volumes against WSDOT/SDOT counts (GEH)
    - 30 loop detectors
    - departLane/departSpeed mix
    - rerouting probability 0.7
    - alleys removed
    - sidewalk speed = street speed
  - **Car-following:** `cc1`–`cc9` are WisDOT VISSIM W99 values (unused, see §2).

### C. GTFS transit (`Simulation/GTFS/seattle_sumo_gtfsData_setup.ipynb`)
Run order (restart the kernel first):
1. **Setup cell "FOR WINDOWS"** (id `5aeac350`):
   - `SUMO_VERSION = "installed"` (reads `SUMO_HOME`, fallback `C:\Program Files (x86)\SUMO`) or `"nightly"` (`C:\Users\dahh2\sumo-nightly\sumo-win64-git`, v1_27_1+0902)
   - overrides `PYTHONPATH`/`PATH`/`sys.path`
   - **Never run the "FOR MAC" cell on Windows.**
2. **`load_gtfs`** (id `6825a4dc`).
3. **Bus filter** (id `d51c3c06-...`): `KEEP_ROUTES` (40 lines), bbox LAT 47.58–47.65, LON −122.37…−122.30 → `gtfs data/kcm_google_transit_downtown.zip`.
4. **Stop snapping** (id `14157d2a`; rewrites the downtown zip in place):
   - direction of travel from `shapes.txt` at `shape_dist_traveled`
   - candidate edges: bus edges within 35 m, heading within 45°, excluding `pseudo*`/motorway; the stop is placed 7 m from the edge ends
   - no bus edge within 35 m, or only cross streets nearby → the stop is dropped
   - trips left with fewer than 2 stops are removed
5. **Rail filter + rail gtfs2pt** (`--date 20260329 --modes=tram`; a Sunday, **[UNVERIFIED]** whether intended).
6. **Bus gtfs2pt** (id `7be7ec6c-...`):
   ```
   gtfs2pt.py -n soheil_seattle_merged_pedspeed.net.xml --gtfs "gtfs data/kcm_google_transit_downtown.zip" --date 20260617 --modes=bus --route-output bus/gtfs_pt_vehicles.add.xml --additional-output bus/gtfs_pt_stops.add.xml --vtype-output bus/vtypes.xml --patched-stops bus/patched_stops.add.xml --use-gtfs-stopids --original-lines --repair --verbose
   ```
- **How gtfs2pt builds routes:** it map-matches stop coordinates (not shapes) and joins consecutive stops by the shortest path.
- **gtfs2pt's own recommendation** (developer reply on #18341): `--stops` from netconvert `--ptstop-output`. Tested on the issue examples: it fixes the C Line case but not the partial-network case. It isn't usable on our older hand-edited net without mapping. Kept our snapping.

### D. Bus riders (`Simulation/ridership/`, run from that folder)
- **Inputs:**
  - the bus outputs (needs `--original-lines`)
  - `data/routeData/kcm/<route>/253/ridershipData.csv` (rapid lines are files 671–678 = A–H)
- **Run:** `python ridership_personflows.py` → `kcm_riders_253_AM_MID.rou.xml` + `_summary.csv` + `_skipped.csv`. Config block: AM 05–09 / MID 09–15, `SIM_WINDOW` 05–12, `FLOW_LEAD` 600 s, `SEED` 42.
- **Rider types:**
  1. **In-area riders:** personFlows (`period="exp(rate)"`) per OD stop pair, only while buses run.
  2. **Exiting riders:** per bus, ride to the route's last edge.
  3. **Entering riders:** `depart="triggered"` (id prefix `rider_in_`).
  
  Full write-up in `ridership/readme.md`.
- **Validation:** tripinfo `personinfo` rides per line vs `_summary.csv` `ridership_boardings`; `--person-summary-output` for waiting counts. These are scratch scripts; the lab has `analyze_yz.py`.

### E. Simulation run / outputs
- **Test runs never write into `new output/`:**
  - set `--additional-files` without the edge-data/loop files
  - redirect `--tripinfo-output`, `--vehroute-output`, `--summary-output`, `--log`
  - SUMO doesn't create folders
- **Bash pattern** (from `Simulation/`):
  ```
  ADD="clean corrected inputs/forMFD_Taz_with_pseudo.add.xml,clean corrected inputs/correct_Alaskan_new_signal_additional_columbia_eb.add.xml,GTFS/rail/tram.add.xml,GTFS/rail/gtfs_pt_stops.add.xml,GTFS/rail/gtfs_pt_vehicles.add.xml,GTFS/bus/bus.add.xml,GTFS/bus/gtfs_pt_stops.add.xml,GTFS/bus/gtfs_pt_vehicles.add.xml"
  "/c/Program Files (x86)/SUMO/bin/sumo.exe" -c gtfs_ridership_vehicular.sumocfg --additional-files "$ADD" --device.rerouting.pre-period 0 --end 43200 --tripinfo-output <scratch>/tripinfo.xml --vehroute-output <scratch>/vehroute.xml --summary-output <scratch>/summary.xml --log <scratch>/log.xml --no-step-log true
  ```
  - Cars only: add `--route-files adjusted_alaskanway_od2trips_psrc_vehicle_trips_converted_taz_calibrated_V3.rou.xml`.
  - No transit vehicles: drop the four `gtfs_pt_*` files.
- **Background runs:** the background-task notice can say exit 0 when SUMO crashed. Record `$?` in a file. For the Windows code, launch from PowerShell with `Start-Process -PassThru` and read `ExitCode`.
- **Long background runs started from a desktop Claude session die if the app quits or restarts.**

### F. Analysis and diagnostic helpers
- `Simulation/ridership/rank_lines_by_ridership.py`: line review order.
- **Scratch scripts from the previous session** (not in the repo; in `C:\Users\dahh2\AppData\Local\Temp\claude\C--Users-dahh2-UW-Projects-Seattle-Sumo-DowntownSeattleSUMO\e6db4f05-eab1-4817-a20b-c7cf02c824d8\scratchpad\`; Temp may be cleaned):
  - `steps/compare.py`: compares runs at different step lengths.
  - `crash/traci_find_step.py`: finds the exact crash step through TraCI.
  - `crash/traci_bisect.py`: stops at a time, dumps all vehicles, removes a subset, steps on.
  - `crash/traci_track.py`: tracks given vehicles and logs ramp mismatches.
  - `crash/traci_census.py`: finds cars whose edge isn't `route[routeIndex]`, using subscriptions. Its mid-route hits right after a periodic reroute are false positives; only the `ri=0` insertion hits are real.
  - Copy any of these into the repo if they're needed again.

## 5. Change history

### Python scripts / notebooks (newest first)
- No code changes since `28e1f84`. 2026-10-16 to 20 was testing and investigation only; outputs are in scratch.
- `ridership/ridership_personflows.py` (new, `28e1f84`): the rider generator. Iterations:
  - `personsPerHour` → `exp(rate)`
  - destinations limited to stops the buses reach
  - flows only while buses run
- `GTFS/seattle_sumo_gtfsData_setup.ipynb` (`28e1f84`): `KEEP_ROUTES` = 40 lines; `--original-lines`.
- `GTFS/seattle_sumo_gtfsData_setup.ipynb` (`6ee46ab`): `SUMO_VERSION` switch; snapping drops stops where only cross streets are nearby.
- `GTFS/seattle_sumo_network_setup.ipynb` (`6ee46ab`): the Windows setup reads `SUMO_HOME`.
- `ridership/rank_lines_by_ridership.py` (new, `6ee46ab`).
- Earlier (`a3337d4`, `358818f`): snapping cell added; nightly setup; gtfs2pt outputs moved to `bus/` and `rail/`.

### Network edits (patch files in `Simulation/GTFS/additional_net/`)
- **Belmont Ave E / Bellevue Pl E** (`6ee46ab`), for route 3:
  - new edges `±621088606` and `±51476458`
  - all-way stop at node `53118280`
  - dead-end U-turns `6479778#7→-6479778#7` and `-6366765#0→6366765#0` deleted
- **E Union St westbound bus block** (`6ee46ab`), for route 2: edge `337673341` (sidewalk + bus lane) → `462700212`.
- **E John St** (`6ee46ab`, `network_fixes.con.xml`), for route 8: `-337668916#0` → `-6463013` lane 1→1.
- **3rd Ave / Vine** (`a3337d4`, `network_fixes.con.xml`): `370785080#0` → `370785080#1` / `243329197#8`.
- **Mercer St** from Elliott Ave W to Warren Ave N (`a3337d4`, two passes): default signals.
- **Columbia St eastbound bus lane** (`358818f`) + the signal file copy `_columbia_eb`.
- **Not a network edit:** in crash tests only, TAZ 7000's source `174699613` was removed in a scratch TAZ copy. It's a dead-end ramp stub that only feeds I-5; worth reviewing as a TAZ source **[UNVERIFIED whether to change]**.

### Commits
- `28e1f84` Add bus riders from ridership for all 40 downtown lines; run single-threaded (2026-10-15)
- `6ee46ab` Review all numbered downtown bus lines; add E Union St and Belmont/Bellevue Pl, SUMO 1.28 (2026-10-09)
- `a3337d4` Add Mercer St, stop snapping and SUMO nightly; move network patches (2026-10-05)
- `da977d7` Add transit-only SUMO config, bus line notes, work log (2026-10-04)
- `358818f` Add eastbound Columbia St bus lane; tidy gtfs2pt outputs (2026-10-03)
- `5721911`, `673a96d`, `39f6a68`, `881480d`, …: user, Soheil and Yiran, before these conversations
- **Uncommitted:**
  - `Simulation/Work_Done.txt` (+31 lines, Oct 15–20)
  - `HANDOFF.md`, `CLAUDE.md` (untracked)
  - generated GTFS/rider outputs (don't commit)

### GitHub issues (filed by the user)
- **eclipse-sumo/sumo#18341** (stop direction): a developer replied (2026-10-16).
  - gtfs2pt ignores shapes (#11327).
  - Our longer-route case "should be investigated as a bug".
  - They suggest `--stops` with OSM stops.
- **eclipse-sumo/sumo#18342** (skip unservable stops on a partial network).
- Examples: `Simulation/GTFS/sumo_issue_examples/`.

## 6. SUMO technical notes
- **SUMO:**
  - **1.28.0** at `C:\Program Files (x86)\SUMO` (Windows installer; the machine-wide `SUMO_HOME`). The lab server has the same version.
  - The nightly v1_27_1+0902 is at `C:\Users\dahh2\sumo-nightly\sumo-win64-git`.
  - Mac version **[UNVERIFIED]**.
- **Tools used:**
  - gtfs2pt, netconvert, sumo / sumo-gui, TraCI and sumolib (Python), netedit (the user), od2trips (demand)
  - not used: duarouter, randomTrips
- **Python:**
  - home: `C:\Users\dahh2\anaconda3\python.exe` (has pandas and rtree; the repo `.venv` lacks rtree). Set `PYTHONIOENCODING=utf-8` for notebook code.
  - lab: Python 3.12.10 (winget, user scope).
  - **Don't pip-install `sumolib`/`traci`** on either machine: the notebook setup cell then strips site-packages.
  - For TraCI scripts, `sys.path.insert(0, SUMO_HOME/tools)`. Don't run gtfs2pt with `python -I`; it can't import its sibling `gtfs2fcd`.
- **Quirks and fixes found:**
  - **The crash (§2):**
    - TAZ-edge insertion mismatch from pre-insertion rerouting with `with-taz`
    - workaround `--device.rerouting.pre-period 0`
    - deterministic per input; `summary.xml`/`log.xml` are buffered, so the crash time read from them is ±a few seconds (TraCI gives the exact step)
  - **SUMO can't reload its own saved state:** 7 inactive actuated programs are written with `state=""` ("Attribute 'state' … is empty"). Delete those lines to load it. A restored run doesn't reproduce the original trajectory.
  - **Multithreading with riders** crashed, hung or corrupted the output, so both configs run single-threaded.
  - **Step length** (05:00–08:00 test, vs 0.1):

    | Step | Faster | Car trip time |
    |---|---|---|
    | 0.25 s | 1.9× | +2.2% |
    | 0.5 s | 2.9× | +6.0% |
    | 1.0 s | 4.1× | +13.1% |

    Buses and riders were nearly unchanged up to 0.5 s; 1.0 s can't run the 3.5 s signal phases exactly. 0.1 was in Soheil's first commit, with no documented reason; his calibration used it.
  - **CCH routing** was slower than astar here; kept astar.
  - **`--original-lines`** → about 2,400 harmless "does not match earlier definitions" warnings.
  - **"Taz usage was requested but no taz present in trip"** (about 1,571 times): harmless **[UNVERIFIED cause]**.
  - **netconvert `-s`:**
    - edges keep their connections, so add turns from former dead ends explicitly
    - a `<delete>` after a split needs a second pass
    - `<tlLogic>` goes before its connections in `.tll.xml`
  - **The signal file overrides the net's programs**, so link counts must match.
  - **Environment variables:**
    - VS Code keeps old environment variables until fully restarted
    - the machine-wide `PYTHONPATH` beats `SUMO_HOME`
    - keep gtfs2pt `-n` paths short (Windows 260-character limit)
  - **PowerShell:** run a quoted exe as `& "C:\...\sumo-gui.exe"`.
- **Baseline warnings:**
  - sumo: 6 "Invalid link … linkMaxDur/linkMinDur" errors for tls `4163983439`, `53088988`, `2062150190` (non-fatal)
  - deprecation warnings for `sloppy-insert` and `ignore-accidents`
  - about 15 teleports in transit-only runs
- **Claude tooling:**
  - **Cross-session messaging** needs Claude Code ≥ v2.1.234 on native Windows. Both ends need Remote Control for cross-machine messages, and messages are plain text.
  - **Desktop app logs:** `C:\Users\dahh2\AppData\Local\Claude\logs\` (`main.log`, `remote-control.log`).

## 7. Decisions and conventions
- **Network patches:** plain-XML files in `additional_net/`, reapplied in order.
  - New edges use OSM ids. Two-way pairs use `spreadType="right"`, one-way edges `"center"`.
  - Lane 0 is the sidewalk; vehicle lanes disallow pedestrian and rail classes.
  - 25 mph = 11.18 m/s.
- **Stop placement:** generic snapping rules, not per-stop pins. Off-network stops are dropped.
- **Line review:** one line, or one through-routed group, at a time with `gtfs_transit_only.sumocfg`, against Apple Maps.
  - Check the feed's `stop_times` before calling a difference a network bug (the feed is summer 2026).
  - Groups: 1+14, 5+21, 2+13, 24+33+124, 28+131+132 (+27).
- **Ridership (user's choices):**
  - AM + MID periods
  - riders enter and leave with buses
  - `--original-lines`
  - keep the old scripts
- **Simulation:**
  - single-threaded; astar routing; step 0.1 (don't change without re-validating)
  - **TAZ-based demand stays**
  - crash workaround via `pre-period 0` (pending the OK to add it to the config)
- **Where work runs:**
  - **Lab server:** long and batch runs (crash/seed/scenario batches, full 05:00–12:00 runs).
  - **This PC:** code, network, notebooks, git, GUI line reviews, short checks. This PC is the source of truth for code.
  - **Coordination:** Remote Control messaging from a fresh session; the user can also relay briefs.
- **Projection:** UTM zone 10N, `netOffset="-546642.00,-5268695.21"`. Use sumolib `convertLonLat2XY`/`convertXY2LonLat`.
- **User preferences:**
  - double-check the file list before commits
  - generated files stay out of git
  - ignore the older uncommitted changes (`run_simulation.py`, `NULL`)
  - log everything in `Work_Done.txt`
  - "make a note" means the GTFS README Known limitations + `Work_Done.txt`/HANDOFF, without code changes
  - works on Windows and Mac

## 8. Open questions and known issues
- **Crash:**
  - lab confirmation pending (Y_full, Z_cars)
  - add the config change after the OK
  - file the SUMO bug report; is the user OK attaching the network and PSRC-derived demand?
- **TAZ 7000 source `174699613`:** a dead-end ramp stub feeding I-5. Should it stay a source? **[UNVERIFIED]**; ask Soheil.
- **Signal timings:** source of Soheil's programs undocumented (SDOT data or tuned?).
- **Car-following model:** W99 parameters unused (Krauss runs). Was W99 intended?
- **Speed limits:** many 30 mph arterials; Seattle downtown is mostly 25 mph **[UNVERIFIED]**.
- **Bus capacity and boarding:** realistic `personCapacity` (40 ft about 80, 60 ft about 115) and `boardingDuration` undecided.
- **Buses spawn and despawn mid-network:** chain trips by `block_id` (gtfs2pt `--join-blocks`, untested) or send buses to a depot.
- **Shortest path instead of the GTFS shape** (route 21). Kaiser & Schmaus 2026 (`Relevent_Papers/3240_Kaiser_and_Schmaus.pdf`):
  - gtfs2pt dropped and distorted trips
  - their fix: duarouter with 3,600 s weights on streets no bus uses, a U-turn penalty, and a whole-trip Dijkstra over stop options
  - their checks: trips planned vs generated per line, and per-trip route/stop equality
  - for us, since KCM has `shapes.txt`: map-match the shapes, or use duarouter `--weight-files`
  - a route-vs-shape and trip-count check task card was proposed (not started)
- **Feed and data vintages:** a GTFS feed newer than summer 2026 exists (2026-09-28), unused; ridership is 2025 Q3; 41 "no matching ridership direction" skips not investigated.
- **Mac:** untested.
- **D Line `LON_MIN`:** undecided.
- **Lines 60 and 106:** not reviewed.
- **Rail:** Sunday date; 2 Line end teleports; no ridership.
- **Network:** 9 sidewalk-only straight movements unchecked; Mercer St signals and crosswalks.
- **Outdated docs:** the root README (network extent); the old parts of the GTFS README.
- **Fresh clone:** `CLAUDE.md` and `HANDOFF.md` are untracked, and the riders and bus outputs are generated. A fresh clone (e.g. the lab) must run the GTFS notebook and `ridership_personflows.py`, or copy those files.
- **Unreviewed paper:** `Relevent_Papers/1-s2.0-S0968090X26004043-main.pdf`.
