# Transit Ridership Integration for SUMO Simulation

_SOHEIL: codes are a little changed after Yiran's commit, the outputs in this folder in the repo are from her work.
Her codes are based on older simulation files where transit trips were coded nicer than what we currently get from 
gtfs2pt in `GTFS` folder. Her work is more of a example of how ridership can be processed but further refinements 
are needed to make it compatible to newer bus/lightrail route/add files. Also, her outputs do not work well as we cannot run `clean_reformed_Seattle.sumocfg` with her new files(personflow generation needs to be fixed)._

## Current method (October 2026): `ridership_personflows.py`
Generates the bus riders used by `gtfs_ridership_vehicular.sumocfg` for all 40 reviewed downtown lines (rapid C, D, E, G, H and 35 numbered lines). It replaces the four-script chain described further below. Those scripts and their outputs (`kcm_personflows_253_AM_with_alighting.rou.xml`, routes 24/33/70/8 only) are kept for reference and were not changed.

Run from this folder, after generating the bus files with the GTFS notebook:
```
python ridership_personflows.py
```
Inputs: `../GTFS/bus/gtfs_pt_vehicles.add.xml` and `gtfs_pt_stops.add.xml`, made by gtfs2pt with `--original-lines` and `--use-gtfs-stopids`; `data/routeData/kcm/<route>/253/ridershipData.csv` (Git LFS). Outputs: `kcm_riders_253_AM_MID.rou.xml`, plus `_summary.csv` (per line, direction and period: ridership boardings vs generated riders, on-board loads) and `_skipped.csv`.

**How riders are generated.** Ridership rows are stop × direction (I/O) × time of day. `trip*` columns are averages per trip; `daily*` columns are totals for that period on a weekday. Periods used: AM (05–09) and MID (09–15), cut to the 05:00–12:00 simulation.
- Each bus is matched to the ridership direction whose stops it shares (stop ids differ by direction).
- Rapid lines are filed under KCM route numbers in the ridership data: 671–678 = A–H Line.
- Destinations: later stops of the same direction, weighted by `tripAlightings`, plus "beyond the network", weighted by `departingLoad` at the last stop in the network (the load leaving the area on board). Only stops that the line's buses in that period actually reach from the origin are used, weighted by the share of buses that do. The 2025 ridership lists some stops the 2026 timetable no longer serves.

Three kinds of riders:
1. **In-area riders** (board and alight inside the network): one `personFlow` per origin/destination stop pair.
   - Riders wait at the stop for any bus of the line (`lines="8"`); SUMO only boards them on a bus that stops at their destination.
   - Rate = `dailyBoardings` × destination share ÷ period hours.
   - Arrivals are random (`period="exp(rate)"`). `personsPerHour` spaces riders evenly and creates at least one rider per flow, which overcounted quiet lines by up to 13×.
   - Flows only run while buses serving that stop pair run (from 10 min before the first), so nobody waits at 05:00 for a 06:00 first bus.
2. **Exiting riders** (board inside, alight after the bus has left the network): tied to one bus, so they ride to the end of its route. Per bus and stop: Poisson(`tripBoardings` × exit share), arriving 1–5 min before the bus.
3. **Entering riders** (on board when a bus enters the network mid-trip): `depart="triggered"` persons inside the bus. Per bus: Poisson(`departingLoad` at the last ridership stop before the network). They alight at one of the bus's stops or stay on to the end of the route.

**Why `--original-lines`.** Without it, gtfs2pt gives each stop pattern / timetable variant its own line id (route 8 became `8`, `8#1` … `8#38`), so riders asking for `lines="8"` could only board 3 of 142 route 8 buses. With it, all buses of a route have `line="8"` (or `C_Line`). Only the `line` attribute changes; routes, stops and vehicle ids are identical. SUMO then prints "line ... does not match earlier definitions, ignoring schedule" warnings, which only affect SUMO's own transit trip planning (not used here).

**Run single-threaded.** With these riders, SUMO 1.28 runs with `threads 4` / `device.rerouting.threads 4` randomly crashed (segmentation fault), hung, or wrote corrupted output (records of different riders spliced together). Single-threaded runs were stable and identical every time, so both GTFS configs now use `threads 1` and `device.rerouting.threads 0`.

**Test (transit only, 05:00–12:00, 2026-10-12).**
- 37,079 riders.
- Simulated boardings 0.99 × ridership (22,004 vs 22,166), most lines within ±10%.
- 0 riders on another line's bus.
- Wait at stop: median 4.6 min, mean 6.2 min, 0.3% over 30 min, longest 61 min.
- Bus trip times unchanged vs no riders (−2 s on average).

**Limits.**
- Schedule and ridership now come from the same service period: ridership 253 (Aug 30, 2025 - Mar 27, 2026) with the KCM fall 2025 schedule (FAL25, sim date 2025-10-15; since 2026-10-22). Only update one of them when matching data for the other exists (see the GTFS README, "Bus schedule and ridership"). With the summer 2026 timetable used before, 120 origin stops had no bus continuing from them in the time window and got no riders; 161 entries are skipped in both cases (see the `_skipped.csv`).
- Lines with only a handful of riders (17, 56, 57, 113, 256, 322) have noisy ratios.
- SUMO's default boarding time is short, so dwell times barely depend on load. A `boardingDuration` on the bus vType would be a later refinement.
- No light rail ridership in the data (the `st` folder has express buses only).

## Overview

This repository contains scripts for integrating public transit ridership data into a SUMO-based multimodal transportation simulation for Downtown Seattle. The workflow focuses on matching observed transit ridership data with the transit network represented in SUMO and generating passenger demand (`personFlow`) files for simulation.

The current implementation focuses on:

* King County Metro (KCM) bus services
* Downtown Seattle simulation region
* AM peak period demand generation
* Stop-level boarding and alighting information
* Passenger flow generation for SUMO transit simulation

---

## Data Sources

Transit ridership data are obtained from:

### Seattle Transit Ridership Project

GitHub Repository:

https://github.com/mes258/seattleTransitRidership

Data Documentation:

https://seattletransitridership.com/frontend/about.html

The project provides route-level and stop-level ridership information for King County Metro and other transit agencies in the Seattle region.

For this study, the ridership data are primarily extracted from:

```text
data/routeData/kcm/<route>/<service_period>/ridershipData.csv
```

where:

* `route` represents the bus route number/name
* `service_period` represents the service change period (e.g., `253` = Aug 30, 2025 - Mar 27, 2026)

The ridership files contain:

* Stop ID
* Route ID
* Time-of-day category
* Average boardings
* Average alightings
* Departing passenger load

Time-of-day categories include:

| Period | Time Range         |
| ------ | ------------------ |
| AM     | 5:00 AM – 9:00 AM  |
| MID    | 9:00 AM – 3:00 PM  |
| PM     | 3:00 PM – 7:00 PM  |
| XEV    | 7:00 PM – 10:00 PM |
| XNT    | 10:00 PM – 5:00 AM |

---

## Workflow

The overall workflow consists of four major steps:

```text
SUMO Network
      │
      ▼
Extract SUMO Bus Stops
      │
      ▼
Match Ridership Data
      │
      ▼
Generate Passenger Demand
      │
      ▼
SUMO Simulation
```

---

## Scripts

### 1. bus_stop_extract.py

Extracts all bus stop IDs from the SUMO additional file.

Input:

```text
forMFD_Taz_with_pseudo.add.xml
```

Output:

```text
sumo_bus_stop_ids.csv
```

The extracted stop IDs are used to identify transit stops located within the simulation network.

---

### 2. bus_route_revise.py

Updates the SUMO route file by adding route line information to transit trips.

Input:

```text
new_bus_link_route.rou.xml
```

Output:

```text
new_bus_link_route_with_line.rou.xml
```

Example:

Before:

```xml
<trip id="1_49195113" type="bus">
```

After:

```xml
<trip id="1_49195113" type="bus" line="1">
```

This step allows passenger demand to be linked to specific transit routes through the SUMO `line` attribute.

---

### 3. ridership_process.py

Matches ridership records with SUMO bus stops.

Inputs:

```text
sumo_bus_stop_ids.csv
data/routeData/kcm/
```

Processing:

* Reads all KCM route folders
* Loads route-level ridership data
* Filters records based on:

  * SUMO stop IDs
  * Time-of-day period (currently AM)
* Identifies routes and stops represented within the simulation area

Output:

```text
kcm_ridership_matched_sumo_stops_253_AM.csv
```

Notes:

The input ridership data path may need to be updated depending on the local directory structure.

---

### 4. ridership_generation.py

Generates SUMO passenger demand files using observed ridership information.

Inputs:

```text
kcm_ridership_matched_sumo_stops_253_AM.csv
new_bus_link_route_with_line.rou.xml
```

Processing:

* Matches ridership records to SUMO transit lines
* Reconstructs stop sequences
* Estimates passenger origins and destinations
* Uses boarding counts to generate passengers
* Uses downstream alighting counts to estimate destination stops
* Estimates initial onboard passenger load for routes entering the simulation region
* Creates SUMO `personFlow` definitions

Output:

```text
kcm_personflows_253_AM_with_alighting.rou.xml
```

Additional Outputs:

```text
estimated_initial_load_by_line_253_AM.csv
skipped_personflows_253_AM_with_alighting.csv
```

---

## Passenger Demand Generation Methodology

### Boardings

Passenger demand is generated from:

```text
tripBoardings
```

which represents average boardings at a stop during a specified time period.

### Alightings

Passenger destinations are estimated using:

```text
tripAlightings
```

at downstream stops along the route.

Downstream alighting counts are converted into probabilities and used to assign destination stops.

### Initial Onboard Load

Because the simulation network represents only a portion of the full transit network, some routes may enter the study area with passengers already onboard.

The initial load is estimated from:

```text
departingLoad
tripBoardings
tripAlightings
```

to maintain consistency between observed boarding and alighting patterns.

---

## Current Assumptions

The current implementation assumes:

1. AM period demand only.
2. Average ridership values represent typical weekday conditions.
3. Passenger destinations are inferred from downstream alighting distributions.
4. No transfer behavior is currently modeled.
5. Transit vehicles and schedules are already available in the SUMO network.

Future improvements may include:

* PM and weekend demand generation
* Explicit transfer modeling
* GTFS schedule integration
* Route-specific calibration
* Transit occupancy validation

---

## Study Area

The simulation focuses on Downtown Seattle:

* North Boundary: Mercer St
* South Boundary: S Atlantic St / Edgar Martinez Dr S
* West Boundary: Alaskan Way
* East Boundary: 12th Ave

Only transit stops located within the simulation network are considered during ridership processing and passenger generation.

---
