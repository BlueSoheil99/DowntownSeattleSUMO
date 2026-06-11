# Transit Ridership Integration for SUMO Simulation

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
* `service_period` represents the service change period (e.g., `253` = 2025 Q3)

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

## Author

Yiran Zhang

Department of Civil & Environmental Engineering

University of Washington
