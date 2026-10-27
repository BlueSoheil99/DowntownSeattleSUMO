---
name: demand-taz
description: Use when working on car demand - PSRC trips, TAZs and pseudo TAZs, od2trips, the adjusted_alaskanway_..._V3.rou.xml route file, rerouting devices, car calibration, or "Taz usage was requested" / insertion / TAZ crash issues.
---
# Car demand (PSRC 2018 -> TAZ trips)

Status: the demand is **not touched** in the GTFS work (project decision). Change it only on an explicit user request; any regeneration is destructive, so ask first.

## Files
- Route file: `Simulation/adjusted_alaskanway_od2trips_psrc_vehicle_trips_converted_taz_calibrated_V3.rou.xml` (~206k trips, 05:00-12:00 used; fromTaz/toTaz trips, no fixed edges).
- TAZs: `Simulation/clean corrected inputs/forMFD_Taz_with_pseudo.add.xml`. TAZ id >= 5000 = pseudo TAZ (network entry/exit for trips from outside downtown). Source/sink edge weights = edge priority (`misc.ipynb`).
- Notebooks: `Demand generation/` (Soheil): step1 read h5 (PSRC trip table -> `psrc_vehicle_trips.csv`, car trips, shared-ride dedupe) -> step2 TAZ filtration/conversion (out-of-network TAZs -> pseudo TAZs, departure shifted by travel time to the boundary) -> step3 generate rou (od2trips per 15 min OD table; vType `passenger` added by hand) -> calibration (V3). Details: root `README.md` "Demand generation".
- PSRC source data is not in git (UW Google Drive link in the README).

## Config settings that matter (gtfs_ridership_vehicular.sumocfg)
- `device.rerouting.with-taz true`, probability 0.7, period 300 s: cars pick source/sink edges and reroute.
- `device.rerouting.pre-period 0`: **keep**. Without it SUMO 1.28 segfaults ~07:13-08:11 (TAZ trip rerouted while waiting for insertion; eclipse-sumo/sumo#18408).
- `threads 1` (multithreading with riders crashes/corrupts). Step 0.1 s. time-to-teleport 150.
- Transit has `has.rerouting.device=false` (a2e02b8): buses/trains must not reroute.
- 3277x "Taz usage was requested but no taz present in trip" warnings are expected (non-TAZ vehicles: transit).

## Rules / pitfalls
- od2trips must use the exact TAZ file the simulation uses; renaming/splitting a TAZ source/sink edge in a net patch breaks demand silently (trips not inserted). Check the TAZ file before touching boundary edges.
- W99 car-following params in the vType are ignored (Krauss runs) - known issue.
- Car results vary between seeds: car teleports ~+-230, mean trip time ~3%. Compare demand/network effects over several seeds.
- Older car-only configs (`clean_reformed_Seattle.sumocfg`, `fullDayTests.sumocfg`) use the same route file: don't edit it in place.
