"""
Generate Link light rail riders (persons) for the GTFS trains made by gtfs2pt, from Sound Transit station boardings.

Data (the "rail" section of Simulation/scenario.json):
- ridership_file: average weekday boardings per station (Sound Transit system performance tracker). Sound Transit
  publishes boardings only: no alightings, no direction, no time of day, no origin-destination pairs.
- downtown_stations: the stations in the study area. Only trips that start or end at one of them are generated.

Method (simple, documented assumptions; see the GTFS README "Link riders"):
- Alightings: daily alightings at a station = its daily boardings (every station is as much a destination as an
  origin over the whole day). TO REVISIT: this ignores the morning flow into downtown and the afternoon flow out;
  needs official alighting / OD data (e.g. Sound Transit or ORCA-based data).
- Destinations (gravity): riders boarding at station o go to every station d that a train of the day reaches after o
  (either direction), in proportion to d's alightings. So the trips o -> d per day = B_o * A_d / sum of A over all
  destinations reachable from o.
- Time of day: share of the daily boardings in AM (05-09) and MID (09-15) from time_of_day_share (assumed from the
  KCM bus ridership), spread evenly inside each period; only the part inside SIM_WINDOW is generated.
- Riders are personFlows with random (Poisson) arrivals that wait at the origin platform for any train of a line
  serving both stations (lines="1_Line" or "1_Line 2_Line"), only while such trains run.
- Not generated: trips between two stations outside downtown that pass through it (they would add load to the
  trains through downtown); riders already on board are created at their real origin station instead.

Needs the rail gtfs2pt output made with --original-lines (train line = "1_Line", "2_Line").
Usage: run from Simulation/ridership/:  python rail_personflows.py
"""
import collections
import csv
import os
import re
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))   # Simulation/ (scenario.py)
import scenario  # noqa: E402

SIM = scenario.load()
R = SIM["rail"]

# ---------------- configuration ----------------
RAIL_VEHICLES = "../GTFS/rail/gtfs_pt_vehicles.add.xml"
RAIL_STOPS = "../GTFS/rail/gtfs_pt_stops.add.xml"
PERIODS = {"AM": (5 * 3600, 9 * 3600), "MID": (9 * 3600, 15 * 3600)}
SIM_WINDOW = (5 * 3600, 12 * 3600)
FLOW_LEAD = 600                       # riders start appearing this many s before the first train serving the pair
OUTPUT = R["rider_prefix"] + ".rou.xml"
SUMMARY = R["rider_prefix"] + "_summary.csv"
SKIPPED = R["rider_prefix"] + "_skipped.csv"
# ------------------------------------------------

# ---- stations and trains ----
station_of = {}                       # trainStop id -> station name
for st in ET.parse(RAIL_STOPS).getroot():
    if st.tag in ("busStop", "trainStop"):
        station_of[st.get("id")] = st.get("name")
root = ET.parse(RAIL_VEHICLES).getroot()
routes = {r.get("id"): [(s.get("busStop") or s.get("trainStop"), float(s.get("until", 0))) for s in r.findall("stop")]
          for r in root.iter("route")}
trains = [{"id": v.get("id"), "route": v.get("route"), "depart": float(v.get("depart")),
           "line": re.sub(r"#\d+$", "", v.get("line"))} for v in root.iter("vehicle")]
if any("#" in v.get("line") for v in root.iter("vehicle")):
    print("WARNING: train lines have #n variants; rerun the rail gtfs2pt cell with --original-lines")
model_stations = set(station_of.values())

# ---- boardings ----
boardings = {}
with open(R["ridership_path"], newline="", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        boardings[row["gtfs_stop_name"]] = float(row["avg_weekday_boardings"])
skipped = []
for name in sorted(set(boardings) - model_stations):
    skipped.append(("", name, "station in the ridership file but not in the rail stops (not in the model)"))
for name in sorted(model_stations - set(boardings)):
    skipped.append(("", name, "station in the model without ridership (no riders from or to it)"))
downtown = [s for s in R["downtown_stations"] if s in model_stations]
for s in R["downtown_stations"]:
    if s not in model_stations:
        print(f"  WARNING: downtown station {s!r} is not a rail stop in the model")
    elif s not in boardings:
        print(f"  WARNING: downtown station {s!r} has no ridership")
print("rail ridership %s: %d stations with boardings, %d in the model; downtown: %s" % (
    R["ridership_label"], len(boardings), len(model_stations & set(boardings)), ", ".join(downtown)))

# ---- which station pairs the trains of the day connect, by which platforms and lines, and when ----
# pair (o, d) -> Counter of (origin platform, destination platform), set of lines, times trains are at o
pairs = collections.defaultdict(lambda: {"plat": collections.Counter(), "lines": set(), "times": []})
for v in trains:
    seq = routes[v["route"]]
    for i, (so, until) in enumerate(seq):
        o = station_of.get(so)
        t = v["depart"] + until
        for sd, _ in seq[i + 1:]:
            d = station_of.get(sd)
            if d is None or d == o:
                continue
            p = pairs[(o, d)]
            p["plat"][(so, sd)] += 1
            p["lines"].add(v["line"])
            p["times"].append(t)

reach = collections.defaultdict(set)   # o -> destinations reachable from o
for (o, d) in pairs:
    reach[o].add(d)

# ---- gravity flows for every pair that starts or ends downtown ----
flows, summary = [], collections.defaultdict(float)
for (o, d), p in sorted(pairs.items()):
    if o not in downtown and d not in downtown:
        continue
    if o not in boardings or d not in boardings:
        continue
    denom = sum(boardings[x] for x in reach[o] if x in boardings)
    if denom <= 0:
        continue
    daily = boardings[o] * boardings[d] / denom          # trips o -> d per weekday (alightings = boardings)
    times = sorted(p["times"])
    for period, (p0, p1) in PERIODS.items():
        a, b = max(p0, SIM_WINDOW[0]), min(p1, SIM_WINDOW[1])
        if a >= b:
            continue
        riders = daily * R["time_of_day_share"][period] * (b - a) / (p1 - p0)
        in_period = [t for t in times if a <= t < b]
        if not in_period or riders <= 0:
            continue
        f0, f1 = max(a, in_period[0] - FLOW_LEAD), min(b, in_period[-1])
        if f1 - f0 < 60:
            f1 = min(b, f0 + 60)
        (so, sd), _ = p["plat"].most_common(1)[0]
        flows.append((f0, f1, riders * 3600.0 / (f1 - f0), so, sd, " ".join(sorted(p["lines"])), o, d, period))
        kind = "downtown->downtown" if o in downtown and d in downtown else (
            "from downtown" if o in downtown else "to downtown")
        summary[(o if o in downtown else d, kind, period)] += riders

# ---- write ----
slug = lambda s: re.sub(r"[^A-Za-z0-9]+", "", s)
out = ET.Element("routes")
for f0, f1, pph, so, sd, lines, o, d, period in sorted(flows):
    pf = ET.SubElement(out, "personFlow", {"id": "link_%s_%s_%s" % (slug(o), slug(d), period),
                                           "begin": "%d" % f0, "end": "%d" % f1, "period": "exp(%.8f)" % (pph / 3600.0)})
    ET.SubElement(pf, "stop", {"busStop": so, "duration": "1"})
    ET.SubElement(pf, "ride", {"busStop": sd, "lines": lines})
ET.indent(out, "    ")
ET.ElementTree(out).write(OUTPUT, encoding="utf-8", xml_declaration=True)

with open(SUMMARY, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["downtown_station", "kind", "period", "riders_in_window"])
    for (s, kind, period), n in sorted(summary.items()):
        w.writerow([s, kind, period, round(n, 1)])
with open(SKIPPED, "w", newline="") as f:
    csv.writer(f).writerows([("line", "station", "reason")] + skipped)

tot = collections.Counter()
for (s, kind, period), n in summary.items():
    tot[kind] += n
print("%s: %d personFlows, %.0f riders expected in %02d:00-%02d:00 (%s)" % (
    OUTPUT, len(flows), sum(tot.values()), SIM_WINDOW[0] // 3600, SIM_WINDOW[1] // 3600,
    ", ".join("%s %.0f" % kv for kv in sorted(tot.items()))))
print("skipped: %d (see %s)" % (len(skipped), SKIPPED))
