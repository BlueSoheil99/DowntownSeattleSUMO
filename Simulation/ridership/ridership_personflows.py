"""
Generate SUMO bus riders (persons) from KCM stop-level ridership for the GTFS buses made by gtfs2pt.

Inputs
- BUS_VEHICLES / BUS_STOPS: gtfs2pt output, made with --original-lines (vehicle line = GTFS route short name,
  spaces -> "_", e.g. "8", "C_Line") and --use-gtfs-stopids (busStop id = gtfs_<stop_id>, extra copies gtfs_<id>#1 ...)
- RIDERSHIP_ROOT: data/routeData/kcm/<route>/<period>/ridershipData.csv (Seattle Transit Ridership project).
  Rows = stop x direction (I/O) x time of day. tripBoardings/tripAlightings/departingLoad are averages per trip,
  dailyBoardings/dailyAlightings are totals for that time-of-day period on a weekday.

Riders (all ride buses only, no walking)
1. In-area riders: board at a stop inside the network and alight at a later stop inside it. personFlows that wait
   at the stop for ANY bus of the line (lines="<line>"); SUMO only lets them board a bus that stops at their
   destination. Rate per hour = dailyBoardings(stop, direction, period) * share of in-area destinations / period hours.
2. Exiting riders: board inside the network, alight after the bus has left it. Tied to one bus (lines=<vehicle id>)
   so they can ride to the end of its route: per bus and stop, Poisson(tripBoardings * exit share) persons, arriving
   at the stop shortly before the bus.
3. Entering riders: already on board when a bus enters the network mid-trip (depart="triggered").
   Per bus, Poisson(departingLoad at the last ridership stop before the first stop in the network); they alight
   at a stop in the network or stay on to the end of the route.
Destinations: downstream stops of the same direction weighted by tripAlightings, plus "beyond the network"
weighted by departingLoad at the last stop in the network (the load that leaves the area on board).

Replaces the older bus_stop_extract.py / ridership_process.py / ridership_generation.py chain (kept for reference).

Usage: run from Simulation/ridership/:  python ridership_personflows.py   (paths and options below)
Run the simulation single-threaded (threads 1, device.rerouting.threads 0): with these riders, SUMO 1.28 crashed,
hung or wrote corrupted output when run with several threads.
"""
import collections
import csv
import math
import os
import random
import re
import xml.etree.ElementTree as ET

# ---------------- configuration ----------------
BUS_VEHICLES = "../GTFS/bus/gtfs_pt_vehicles.add.xml"
BUS_STOPS = "../GTFS/bus/gtfs_pt_stops.add.xml"
RIDERSHIP_ROOT = "data/routeData/kcm"               # Git LFS (git lfs pull)
SERVICE_CHANGE = "253"                           # Aug 30, 2025 - Mar 27, 2026 (matches the FAL25 bus schedule); newest available
PERIODS = {"AM": (5 * 3600, 9 * 3600), "MID": (9 * 3600, 15 * 3600)}   # ridership time-of-day periods (s)
SIM_WINDOW = (5 * 3600, 12 * 3600)               # only generate riders inside this window
OUTPUT = "kcm_riders_253_AM_MID.rou.xml"
SUMMARY = "kcm_riders_253_AM_MID_summary.csv"
SKIPPED = "kcm_riders_253_AM_MID_skipped.csv"
ENTERING_RIDERS = True                           # riders already on board when a bus enters the network
EXITING_RIDERS = True                            # riders who stay on until the bus leaves the network
ARRIVE_BEFORE_BUS = (60, 300)                    # exiting riders reach their stop this many s before the bus
FLOW_LEAD = 600                                  # in-area riders start appearing this many s before the first bus
SEED = 42
# rapid lines are filed under KCM route numbers in the ridership data
RIDERSHIP_ROUTE = {"A_Line": "671", "B_Line": "672", "C_Line": "673", "D_Line": "674",
                   "E_Line": "675", "F_Line": "676", "G_Line": "677", "H_Line": "678"}
# ------------------------------------------------

rng = random.Random(SEED)


def poisson(lam):
    """Poisson sample (Knuth; lam is small here)."""
    if lam <= 0:
        return 0
    L, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= rng.random()
        if p <= L:
            return k
        k += 1


def base_id(stop_id):
    """gtfs_3589#1 -> 3589"""
    return stop_id[len("gtfs_"):].split("#")[0]


def period_of(t):
    for name, (a, b) in PERIODS.items():
        if a <= t < b:
            return name
    return None


# ---- buses ----
root = ET.parse(BUS_VEHICLES).getroot()
routes = {}
for r in root.iter("route"):
    stops = [(s.get("busStop"), float(s.get("until", 0))) for s in r.findall("stop") if s.get("busStop")]
    routes[r.get("id")] = {"edges": r.get("edges").split(), "stops": stops}
vehicles = [{"id": v.get("id"), "route": v.get("route"), "depart": float(v.get("depart")), "line": v.get("line")}
            for v in root.iter("vehicle")]

# ---- ridership ----
def load_ridership(line):
    route_num = RIDERSHIP_ROUTE.get(line, line)
    path = os.path.join(RIDERSHIP_ROOT, route_num, SERVICE_CHANGE, "ridershipData.csv")
    if not os.path.exists(path):
        return None
    rows = collections.defaultdict(dict)   # (direction, period) -> stopId -> row
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            if row["timeOfDay"] not in PERIODS:
                continue
            for k in ("tripBoardings", "tripAlightings", "departingLoad", "dailyBoardings", "dailyAlightings"):
                row[k] = float(row[k] or 0)
            row["order"] = int(row["stopOrderNum"])
            rows[(row["direction"], row["timeOfDay"])][row["stopId"]] = row
    return rows


ridership = {}
skipped = []
for line in sorted({v["line"] for v in vehicles}):
    ridership[line] = load_ridership(line)
    if ridership[line] is None:
        skipped.append((line, "", "", "no ridership file for period %s" % SERVICE_CHANGE))


def direction_of(line, stop_ids):
    """ridership direction (I/O) sharing the most stops with this bus's stops"""
    rows = ridership.get(line)
    if not rows:
        return None
    best, best_n = None, 0
    for d in ("I", "O"):
        ids = set()
        for p in PERIODS:
            ids |= set(rows.get((d, p), {}))
        n = len(ids & set(stop_ids))
        if n > best_n:
            best, best_n = d, n
    return best


# group buses by (line, direction); collect the network stops each direction uses (and which stop copy)
groups = collections.defaultdict(list)
stop_copy = collections.defaultdict(collections.Counter)   # (line, dir, base id) -> busStop ids used
for v in vehicles:
    st = routes[v["route"]]["stops"]
    d = direction_of(v["line"], [base_id(s) for s, _ in st])
    if d is None:
        skipped.append((v["line"], v["id"], "", "no matching ridership direction"))
        continue
    v["dir"] = d
    groups[(v["line"], d)].append(v)
    for s, _ in st:
        stop_copy[(v["line"], d, base_id(s))][s] += 1


def stats(line, d, period):
    """per-direction/period ridership restricted to the stops the buses serve in the network"""
    rows = ridership[line].get((d, period), {})
    in_net = sorted((r for sid, r in rows.items() if (line, d, sid) in stop_copy), key=lambda r: r["order"])
    if not in_net:
        return None
    first, last = in_net[0]["order"], in_net[-1]["order"]
    upstream = [r for r in rows.values() if r["order"] < first]
    enter_load = max(upstream, key=lambda r: r["order"])["departingLoad"] if upstream else 0.0
    exit_load = in_net[-1]["departingLoad"] if any(r["order"] > last for r in rows.values()) else 0.0
    return {"stops": in_net, "enter_load": enter_load, "exit_load": exit_load}


def destinations(st, origin_order, reach=None, serves=None):
    """[(base stop id or None for 'beyond the network', weight)] for a rider boarding at origin_order.
    reach: {destination: share of the buses at the origin that later stop there} -- riders only go where the
    buses of this period actually go (the 2025 ridership can list stops the 2026 timetable no longer serves).
    serves: set of stops of one particular bus (riders already on it)."""
    dest = []
    for r in st["stops"]:
        if r["order"] <= origin_order or r["tripAlightings"] <= 0:
            continue
        share = 1.0
        if reach is not None:
            share = reach.get(r["stopId"], 0.0)
        if serves is not None and r["stopId"] not in serves:
            share = 0.0
        if share > 0:
            dest.append((r["stopId"], r["tripAlightings"] * share))
    if st["exit_load"] > 0:
        dest.append((None, st["exit_load"]))
    return dest


def reach_shares(buses, period, window):
    """origin -> {destination: share of the buses stopping at origin (in this period) that later stop at destination},
    and (origin, destination) -> (first, last) time such a bus is at the origin"""
    at_origin = collections.Counter()
    pairs = collections.Counter()
    times = {}
    for v in buses:
        seq = routes[v["route"]]["stops"]
        ids = [base_id(s) for s, _ in seq]
        for i, (s, until) in enumerate(seq):
            t = v["depart"] + until
            if period_of(t) != period or not (window[0] <= t < window[1]):
                continue
            at_origin[ids[i]] += 1
            for later in set(ids[i + 1:]):
                pairs[(ids[i], later)] += 1
                t0, t1 = times.get((ids[i], later), (t, t))
                times[(ids[i], later)] = (min(t0, t), max(t1, t))
    out = collections.defaultdict(dict)
    for (o, d), n in pairs.items():
        out[o][d] = n / at_origin[o]
    return out, times


def pick(dest):
    total = sum(w for _, w in dest)
    x = rng.random() * total
    for sid, w in dest:
        x -= w
        if x <= 0:
            return sid
    return dest[-1][0]


flows, persons = [], []
summary = []
for (line, d), buses in sorted(groups.items()):
    for period, (p0, p1) in PERIODS.items():
        st = stats(line, d, period)
        if st is None:
            continue
        a, b = max(p0, SIM_WINDOW[0]), min(p1, SIM_WINDOW[1])
        if a >= b:
            continue
        hours = (p1 - p0) / 3600.0
        rec = {"line": line, "dir": d, "period": period, "stops_in_net": len(st["stops"]),
               "ridership_boardings": sum(r["dailyBoardings"] for r in st["stops"]) * (b - a) / (p1 - p0),
               "flow_riders": 0.0, "exiting_riders": 0, "entering_riders": 0, "enter_load_per_trip": st["enter_load"],
               "exit_load_per_trip": st["exit_load"]}
        reach, pair_times = reach_shares(buses, period, (a, b))
        # 1. in-area riders: personFlows per origin/destination stop pair
        for r in st["stops"]:
            if r["stopId"] not in reach and r["dailyBoardings"] > 0:
                skipped.append((line, d, r["stopId"], "%s: no bus of this line continues from this stop in the window" % period))
                continue
            dest = destinations(st, r["order"], reach=reach.get(r["stopId"], {}))
            total = sum(w for _, w in dest)
            if r["dailyBoardings"] <= 0 or total <= 0:
                if r["dailyBoardings"] > 0:
                    skipped.append((line, d, r["stopId"], "%s: no downstream destination" % period))
                continue
            origin = stop_copy[(line, d, r["stopId"])].most_common(1)[0][0]
            for sid, w in dest:
                if sid is None:
                    continue
                pph = r["dailyBoardings"] * w / total / hours
                riders = pph * (b - a) / 3600.0
                # only while buses serving this pair run (from FLOW_LEAD s before the first to the last one),
                # with the same number of riders: no one waiting at 05:00 for a line whose first bus comes at 06:00
                t0, t1 = pair_times[(r["stopId"], sid)]
                f0, f1 = max(a, t0 - FLOW_LEAD), min(b, t1)
                if f1 - f0 < 60:
                    f1 = min(b, f0 + 60)
                flows.append((f0, f1, riders * 3600.0 / (f1 - f0), origin, stop_copy[(line, d, sid)].most_common(1)[0][0], line, period))
                rec["flow_riders"] += riders
        # 2./3. per-bus riders
        for v in buses:
            st_v = routes[v["route"]]["stops"]
            t_first = v["depart"] + st_v[0][1]
            last_edge = routes[v["route"]]["edges"][-1]
            if ENTERING_RIDERS and st["enter_load"] > 0 and period_of(t_first) == period and a <= t_first < b:
                order = {r["stopId"]: r["order"] for r in st["stops"]}
                first_order = min((order[base_id(s)] for s, _ in st_v if base_id(s) in order), default=None)
                if first_order is not None:
                    own_stop = {base_id(s): s for s, _ in st_v}
                    dest = destinations(st, first_order - 1, serves=set(own_stop))
                    for _ in range(poisson(st["enter_load"])):
                        sid = pick(dest)
                        # beyond the network, or a stop this bus variant skips: stay on to the end of the route
                        to = {"busStop": own_stop[sid]} if sid in own_stop else {"to": last_edge}
                        persons.append(("triggered", v["id"], None, to))
                        rec["entering_riders"] += 1
            if EXITING_RIDERS and st["exit_load"] > 0:
                rows = {r["stopId"]: r for r in st["stops"]}
                for s, until in st_v:
                    r = rows.get(base_id(s))
                    t = v["depart"] + until
                    if r is None or period_of(t) != period or not (a <= t < b):
                        continue
                    dest = destinations(st, r["order"], serves={base_id(x) for x, _ in st_v})
                    total = sum(w for _, w in dest)
                    if total <= 0:
                        continue
                    for _ in range(poisson(r["tripBoardings"] * st["exit_load"] / total)):
                        dep = max(SIM_WINDOW[0], t - rng.uniform(*ARRIVE_BEFORE_BUS))
                        persons.append((dep, v["id"], s, {"to": last_edge}))
                        rec["exiting_riders"] += 1
        summary.append(rec)

# ---- write ----
out = ET.Element("routes")
n = 0
for dep, veh, origin, to in sorted((p for p in persons if p[0] == "triggered"), key=lambda p: p[1]):
    pe = ET.SubElement(out, "person", {"id": "rider_in_%d" % n, "depart": "triggered"})
    ET.SubElement(pe, "ride", dict(to, lines=veh))
    n += 1
items = [("flow", f[0], f) for f in flows] + [("person", p[0], p) for p in persons if p[0] != "triggered"]
for kind, t, x in sorted(items, key=lambda i: i[1]):
    if kind == "flow":
        a, b, pph, origin, dest, line, period = x
        pf = ET.SubElement(out, "personFlow", {"id": "rider_%s_%s_%s_%s" % (line, origin[5:], dest[5:], period),
                                                # random (Poisson) arrivals at the average rate: personsPerHour
                                                # spaces riders evenly and makes at least one per flow, even at 0.01/h
                                                "begin": "%d" % a, "end": "%d" % b, "period": "exp(%.8f)" % (pph / 3600.0)})
        ET.SubElement(pf, "stop", {"busStop": origin, "duration": "1"})
        ET.SubElement(pf, "ride", {"busStop": dest, "lines": line})
    else:
        dep, veh, origin, to = x
        pe = ET.SubElement(out, "person", {"id": "rider_out_%d" % n, "depart": "%.1f" % dep})
        ET.SubElement(pe, "stop", {"busStop": origin, "duration": "1"})
        ET.SubElement(pe, "ride", dict(to, lines=veh))
        n += 1
ET.indent(out, "    ")
ET.ElementTree(out).write(OUTPUT, encoding="utf-8", xml_declaration=True)

with open(SUMMARY, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(summary[0]))
    w.writeheader()
    w.writerows(summary)
with open(SKIPPED, "w", newline="") as f:
    csv.writer(f).writerows([("line", "direction_or_vehicle", "stop", "reason")] + skipped)

tot = lambda k: sum(r[k] for r in summary)
print("%s: %d personFlows, %d per-bus riders (%d entering on board, %d exiting)" % (
    OUTPUT, len(flows), len(persons), tot("entering_riders"), tot("exiting_riders")))
print("ridership boardings in window %.0f | in-area flow riders %.0f + exiting %d = %.0f" % (
    tot("ridership_boardings"), tot("flow_riders"), tot("exiting_riders"), tot("flow_riders") + tot("exiting_riders")))
print("skipped: %d (see %s)" % (len(skipped), SKIPPED))
