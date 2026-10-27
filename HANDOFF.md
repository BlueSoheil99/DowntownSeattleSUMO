# HANDOFF: Downtown Seattle SUMO digital twin (2026-10-27)
Repo `BlueSoheil99/DowntownSeattleSUMO`, `main`, HEAD `c8061f8` = origin. Detail: `Simulation/GTFS/README.md`, `Simulation/ridership/readme.md`, log `Simulation/Work_Done.txt` (grep, don't read whole). Archive: `docs/HANDOFF_2026-10-20_full.md`.

## 1. Role
You are a lab/research assistant helping build a digital twin of downtown Seattle in SUMO with multiple transit modes. Your responsibilities:
- Write and maintain Python scripts for importing maps (OSM), travel demand, ridership, GTFS bus routes/stops, and other inputs.
- Edit .net.xml and related network files so the street network matches real life (lanes, turn restrictions, signals, bus lanes, stops).
- Give technical feedback, and explain any pipeline in the project in detail when asked.
- Keep the working log and README files up to date as changes are made.
- Ask before making destructive changes (deleting files, regenerating the network, force-pushing).
Rules in `CLAUDE.md` (commit OK + stage by name; runs > 15 min go to the lab; test sims never write to `Simulation/new output/`; token rules).

## 2. Project status snapshot
**Now:** phase 1 (bus routes + ridership) is done apart from the report. Baseline = S2 (`df4663c`): shape-based bus routes, no transit rerouting, 3rd & Yesler fixes. Seed test: S2 vs X1 differences are seed noise. Next: report draft.
**Sessions:** primary home = `HOME_DTS_Current`. Lab = `lab-server_sumo` (Remote Control; replies to the sender, so a new primary messages it with its name). Outstanding with the lab: nothing.
**Uncommitted / pending:** only regenerated files with timestamp-only changes (rail outputs, vtypes, downtown zips) and old junk; don't commit. New, uncommitted (multi-agent setup, 2026-10-27): `Simulation/tools/summarize_run.py`, `.claude/skills/{net-patch,gtfs-pipeline,demand-taz,sim-analysis}/SKILL.md`; next: lab checks the script on S2 outputs, then agent definitions + CLAUDE.md delegation rules. User hasn't answered: robustness fixes (only if other periods run).
**Works:** cars + 40 KCM bus lines + Link 1/2 Line + bus and Link riders, 05:00-12:00: `sumo -c gtfs_ridership_vehicular.sumocfg` from `Simulation/` (section 6).
**Next steps:**
1. Report draft for the research write-up (baseline S2; lab outputs test_S2, test_S2_s2, test_S2_s3; report over 3 seeds).
2. Optional: where line 21 teleports on its new route (2-3 per seed).
3. Phase 2 (network + signals): junction 53129291, 3rd SB / Yesler EB one lane, real or flow-based signal timings.
4. Robustness fixes from the modularity tests, only if other periods are run.

## 3. Repo structure
(H) hand-edited, (G) generated.
- Root: `CLAUDE.md`, `HANDOFF.md`, `.claude/commands/handoff.md` (`/handoff`), `.claude/hooks/restore_context.py` + `.claude/settings.json` (SessionStart hook: HANDOFF title + section 2 + 3 newest log headers, < 2 KB). `.claude/skills/`: net-patch, gtfs-pipeline, demand-taz, sim-analysis (procedures, loaded on demand). `Simulation/tools/summarize_run.py` (H): run summary / comparison table. `docs/`: archived handoff.
- `Simulation/scenario.json` + `scenario.py` (H): bus feed, sim date, ridership period, lines, rail section.
- `Simulation/gtfs_ridership_vehicular.sumocfg` (full), `gtfs_transit_only.sumocfg` (H). `clean_reformed_Seattle.sumocfg`, `fullDayTests.sumocfg`: older car-only configs, don't break.
- `Simulation/adjusted_alaskanway_..._V3.rou.xml` (G, Soheil): car demand. `clean corrected inputs/`: TAZs, signal file `correct_Alaskan_new_signal_additional_columbia_eb.add.xml` (H, GTFS configs only).
- `Simulation/GTFS/`: `seattle_sumo_gtfsData_setup.ipynb` (GTFS pipeline), `seattle_sumo_network_setup.ipynb` (network + ped-speed cell `a7d6fe60`), `soheil_seattle_merged.net.xml` + `_pedspeed.net.xml` (G, tracked), `additional_net/` (patches; `drafts/signal_3rd_james_90s.diff` rejected), `route_buses_by_shape.py` (H), `check_bus_routes_vs_shapes.py` (H) -> `route_check/` (G), `bus/` + `rail/` gtfs2pt outputs (G, tracked reference set; `bus/patched_stops.add.xml` H), `vtype_by_line.csv` (H, LFS).
- `Simulation/ridership/`: `ridership_personflows.py`, `rail_personflows.py` (H) -> `kcm_riders_253_AM_MID.rou.xml`, `link_riders_2026-04_05_AM_MID.rou.xml` (G, tracked).

## 4. Pipelines (details in GTFS README)
- **Network:** committed `soheil_seattle_merged.net.xml` + patches in README order, ending with `third_yesler.{edg,con}.xml` then `ped_only_paths.{edg,con}.xml`; then ped-speed (`netconvert -s soheil_seattle_merged.net.xml -e additional_net/ped_speed_patch.edg.xml -o soheil_seattle_merged_pedspeed.net.xml`). Signal changes go in the signal file (`third_yesler_signal.diff`). After any change: delete `GTFS/resources/` and `GTFS/input/`, rerun GTFS cells + riders.
- **GTFS cells (from `GTFS/`, restart kernel):** Windows setup `5aeac350` -> `6825a4dc` load -> `d51c3c06` bus filter -> `14157d2a` stop snapping -> `fdc0ae87` rail filter -> `d0a8958f` rail gtfs2pt -> `7be7ec6c` bus gtfs2pt -> `5b1e7c2a` shape routing (`route_buses_by_shape.py`, MIN_GAIN 150 m) -> `cf9bfc97` Link vTypes -> `68b27bce` bus vTypes. Headless: IPython with anaconda first on PATH.
- **Riders:** from `ridership/`: `python ridership_personflows.py`, `python rail_personflows.py`.
- **Check:** `GTFS/check_bus_routes_vs_shapes.py` (needs a shapely+pyproj venv; README "Route check").

## 5. Change history (newest first; full log in Work_Done.txt)
- `c8061f8` S2 + seed-test log. `df4663c` shape routing MIN_GAIN 30 -> 150 m (50 routes: 21, H, 56, 57, 113, 125, 3, 49). `f6be9ca` `route_buses_by_shape.py` + cell `5b1e7c2a` (route check wrong-street trips 108 -> 0).
- `a2e02b8`: `has.rerouting.device=false` on bus + Link vTypes; 3rd & Yesler (tls `53071891`): deleted gneE171_1 -> gneE495_1, 90 s signal (was 154.5 s, 3rd SB 12% green); `6449188#0` spreadType right (lanes met 6.4 m offset at `gneE173`); `gneE170` + `gneE743` pedestrian-only (tls `764028198` 7 -> 5 links; 101/102/150 via `gneE458`); bus outputs regenerated; 15-min lab rule.
- `4c231e2` W2 results, token rules. `9236c7b` hook digest. `8fa720a` handoff automation.
- `fe0d81f` Link riders, weekday rail date. `1d75d16` scenario.json. `30b4bbc` bus feed FAL25. `f4e03d9` reference set. `bdd4f1a` vTypes by line, route check. `33ce63f` `pre-period 0` (crash fix, sumo#18408). `28e1f84` bus riders. Older: line reviews, Columbia EB bus lane, Mercer St, E Union, Belmont.

## 6. SUMO technical notes
- Run from `Simulation/`: `sumo -c gtfs_ridership_vehicular.sumocfg` or `gtfs_transit_only.sumocfg`. GUI: `& "C:\Program Files (x86)\SUMO\bin\sumo-gui.exe" -c ...`. Full run ~1.2 h alone / 2.7 h in parallel on the lab; 05:00-09:00 with cars ~2 h here; transit-only 05:00-12:00 ~7 min here.
- Lab clone `C:\Users\dharoot\Documents\iUTS_Projects\DT_Seattle_SUMO_git`, notes `lab_notes/` (index `README_LAB.md`). Its user approves `.claude/` changes on pull.
- SUMO 1.28.0, `C:\Program Files (x86)\SUMO` (SUMO_HOME), same on lab. Mac **[UNVERIFIED]**.
- Python: `C:\Users\dahh2\anaconda3\python.exe` (pandas, rtree; no shapely/pyproj). Git Bash `python` is another interpreter without rtree. Don't pip-install sumolib/traci.
- Keep `pre-period 0`; `threads 1`. The signal file overrides net programs: link counts must match after network edits.
- Git Bash `sed -i` strips CRs (Work_Done, READMEs, HANDOFF, signal files are CRLF): use Python. `patch` needs `--binary` for the CRLF signal diffs and the file name given explicitly (spaces).
- Baseline log errors: 6 "Invalid link" (tls 4163983439, 53088988, 2062150190), harmless.

## 7. Decisions and conventions
- Schedule and ridership from the same period: bus FAL25 + period 253, rail Apr-May 2026. TAZ demand stays. Step 0.1 s.
- Network edits only as patch files, tested on a copy. Generic stop snapping, no per-stop pins (pinning crashes gtfs2pt when the pinned edge isn't on the map-matched route).
- Buses/trains never reroute in SUMO. Shape routing changes a leg only for >= 150 m gain.
- Report results over several seeds (car teleports vary ~230, car trip ~3% between seeds).
- Phase 2 items stay out of phase 1 (user, 2026-10-23).
- User: dense factual answers, mark unknowns [UNVERIFIED], works on Windows and Mac.

## 8. Open questions and known issues
- Junction 53129291 (right_before_left, near the gneE743 plaza): warnings 35 -> 110 -> 297; cars likely diverted from the plaza.
- Line 21 new route: 2-3 bus teleports per seed (location unknown).
- Alaskan Way geometry 35-38 m from GTFS shapes (198 route-check artifact flags).
- Link: alightings = boardings, through riders not generated, Downtown Redmond terminus boarding (6 riders).
- 161 skipped bus ridership entries not investigated; buses appear/disappear at trip ends (`--join-blocks` untested).
- Signal timing source undocumented; W99 params unused (Krauss runs); many 30 mph arterials.
- GitHub: #18341, #18342, #18408 open.
