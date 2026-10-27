"""Summarise a SUMO run in ~30 lines (or compare two runs).

Run from Simulation/:
    python tools/summarize_run.py "new output"
    python tools/summarize_run.py runA_dir --compare runB_dir
    python tools/summarize_run.py runA_dir@gtfsA --compare runB_dir@gtfsB
    python tools/summarize_run.py runA_dir --json runA_metrics.json

Reads <dir>/tripinfo_output.xml or tripinfo.xml (streamed) and <dir>/log.xml.
"dir@gtfs" uses <gtfs>/bus and <gtfs>/rail gtfs_pt_vehicles.add.xml for that run
(default GTFS/), e.g. the transit files of the run's own commit.
Bus targets: ridership/kcm_riders_253_AM_MID_summary.csv (05:00-12:00, so short
runs give low ratios). Boardings exclude rider_in_* persons (already on board
when the bus enters the network) and link_* persons. Link expected riders come
from the personFlows in the Link .rou.xml (exp(rate) x overlap with --window).
"""
import argparse
import csv
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict

SIM = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEF_GTFS = os.path.join(SIM, "GTFS")
DEF_BUS_RIDERS = os.path.join(SIM, "ridership", "kcm_riders_253_AM_MID_summary.csv")
DEF_LINK_ROU = os.path.join(SIM, "ridership", "link_riders_2026-04_05_AM_MID.rou.xml")
TRIPINFO_NAMES = ("tripinfo_output.xml", "tripinfo.xml")
MIN_LINE_RIDERS = 100   # lines checked for +-10%
TOP = 5


def vehicle_lines(path):
    """vehicle id -> line, from a gtfs_pt_vehicles file."""
    out = {}
    if not os.path.exists(path):
        return out
    for _, el in ET.iterparse(path):
        if el.tag == "vehicle":
            out[el.get("id")] = el.get("line", "")
        el.clear()
    return out


def bus_targets(path):
    t = defaultdict(float)
    if os.path.exists(path):
        with open(path, newline="") as f:
            for r in csv.DictReader(f):
                t[r["line"]] += float(r["ridership_boardings"] or 0)
    return t


def link_target(path, b, e):
    """Expected Link riders: sum over personFlows of rate x overlap with [b, e]."""
    if not os.path.exists(path):
        return 0.0
    tot = 0.0
    for _, el in ET.iterparse(path):
        if el.tag == "personFlow":
            fb, fe = float(el.get("begin", 0)), float(el.get("end", e))
            span = max(0.0, min(fe, e) - max(fb, b))
            per = el.get("period", "")
            if per.startswith("exp("):
                tot += float(per[4:-1]) * span
            elif el.get("number"):
                tot += float(el.get("number")) * span / max(fe - fb, 1e-9)
            elif per:
                tot += span / float(per)
            elif el.get("perHour"):
                tot += float(el.get("perHour")) * span / 3600
        if el.tag in ("personFlow", "person", "vehicle", "trip"):
            el.clear()
    return tot


def norm_msg(line):
    """Warning/error type with ids and numbers stripped."""
    s = re.sub(r"'[^']*'", "X", line.strip())
    return re.sub(r"[-+]?\d[\d.,#_:]*", "N", s)[:120]


def kind(vid, bus, rail):
    if vid in bus:
        return "bus"
    if vid in rail:
        return "rail"
    return "car"


def read_tripinfo(path, bus, rail):
    m = {"car_n": 0, "car_dur": 0.0, "car_loss": 0.0, "bus_n": 0, "rail_n": 0,
         "transit_rerouted": 0, "persons": 0, "link_persons": 0}
    rides = Counter()                      # line -> rides (boardings)
    line_dur = defaultdict(list)
    for _, el in ET.iterparse(path):
        if el.tag == "tripinfo":
            vid = el.get("id")
            k = kind(vid, bus, rail)
            dur = float(el.get("duration", 0))
            if k == "car":
                m["car_n"] += 1
                m["car_dur"] += dur
                m["car_loss"] += float(el.get("timeLoss", 0))
            else:
                m[k + "_n"] += 1
                line_dur[(bus.get(vid) or rail.get(vid))].append(dur)
                if int(el.get("rerouteNo", 0) or 0) > 0:
                    m["transit_rerouted"] += 1
            el.clear()
        elif el.tag == "personinfo":
            m["persons"] += 1
            pid = el.get("id", "")
            if pid.startswith("link_"):
                m["link_persons"] += 1
            if pid.startswith(("rider_in_", "link_")):
                el.clear()           # on board at entry / Link riders: not bus boardings
                continue
            for ride in el.iter("ride"):
                v = ride.get("vehicle", "")
                if v in bus:
                    rides[bus[v]] += 1
                elif v in rail:
                    rides[rail[v]] += 1
            el.clear()
    m["car_mean_dur"] = m["car_dur"] / m["car_n"] if m["car_n"] else 0
    m["car_mean_loss"] = m["car_loss"] / m["car_n"] if m["car_n"] else 0
    del m["car_dur"], m["car_loss"]
    m["line_mean_dur"] = {k: sum(v) / len(v) for k, v in line_dur.items() if k}
    return m, rides


TELE = re.compile(r"Teleporting vehicle '([^']+)'; waited too long \(([^)]+)\), lane='([^']*)'")
PTELE = re.compile(r"[Tt]eleport\w* person '([^']+)'")
SKIP = re.compile(r"[Vv]ehicle '([^']+)'.*skip\w* stop.*?(?:lane|busStop) '([^']+)'")
RBL = re.compile(r"[Ss]uspicious right_before_left junction '([^']+)'")


def read_log(path, bus, rail):
    tele = Counter()
    tele_reason = Counter()
    bus_edges = Counter()
    car_edges = Counter()
    rbl = Counter()
    skips = Counter()
    types = Counter()
    m = {"person_teleports": 0, "emergency_braking": 0, "errors": 0, "warnings": 0}
    if not os.path.exists(path):
        return m
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            if line.startswith("Warning"):
                m["warnings"] += 1
                types[norm_msg(line)] += 1
            elif line.startswith("Error"):
                m["errors"] += 1
                types[norm_msg(line)] += 1
            if "Teleporting vehicle" in line:
                t = TELE.search(line)
                if t:
                    k = kind(t.group(1), bus, rail)
                    tele[k] += 1
                    tele_reason[(k, t.group(2))] += 1
                    edge = t.group(3).rsplit("_", 1)[0]
                    (bus_edges if k == "bus" else car_edges if k == "car" else Counter())[edge] += 1
                continue
            if PTELE.search(line):
                m["person_teleports"] += 1
            elif "emergency braking" in line:
                m["emergency_braking"] += 1
            elif "right_before_left" in line:
                r = RBL.search(line)
                rbl[r.group(1) if r else "?"] += 1
            elif "skip" in line and "stop" in line:
                s = SKIP.search(line)
                skips[s.group(2) if s else "?"] += 1
    m.update({
        "teleports": sum(tele.values()), "teleports_car": tele["car"],
        "teleports_bus": tele["bus"], "teleports_rail": tele["rail"],
        "bus_wrong_lane": tele_reason[("bus", "wrong lane")],
        "skipped_stops": sum(skips.values()),
        "right_before_left": sum(rbl.values()),
        "top_bus_tele_edges": bus_edges.most_common(TOP),
        "top_car_tele_edges": car_edges.most_common(TOP),
        "top_rbl_junctions": rbl.most_common(TOP),
        "top_skipped_stops": skips.most_common(TOP),
        "msg_types": dict(types),
    })
    return m


def find_tripinfo(d, name):
    for n in ([name] if name else TRIPINFO_NAMES):
        p = os.path.join(d, n)
        if os.path.exists(p):
            return p
    sys.exit("no %s in %s" % (" / ".join([name] if name else TRIPINFO_NAMES), d))


def summarize(spec, a):
    d, _, gtfs = spec.partition("@")
    gtfs = gtfs or a.gtfs
    bus = vehicle_lines(os.path.join(gtfs, "bus", "gtfs_pt_vehicles.add.xml"))
    rail = vehicle_lines(os.path.join(gtfs, "rail", "gtfs_pt_vehicles.add.xml"))
    if not bus:
        print("WARNING: no bus vehicles in %s/bus; buses counted as cars" % gtfs)
    m, rides = read_tripinfo(find_tripinfo(d, a.tripinfo), bus, rail)
    m.update(read_log(os.path.join(d, a.log), bus, rail))
    targets = bus_targets(a.bus_riders)
    bus_rides = sum(n for ln, n in rides.items() if ln in targets)
    m["bus_boardings"] = bus_rides
    m["bus_boarding_ratio"] = bus_rides / sum(targets.values()) if targets else 0
    big = {ln: t for ln, t in targets.items() if t >= MIN_LINE_RIDERS}
    ratios = {ln: rides.get(ln, 0) / t for ln, t in big.items()}
    m["lines_within_10pct"] = sum(1 for r in ratios.values() if abs(r - 1) <= 0.10)
    m["lines_checked"] = len(big)
    m["lines_outside_10pct"] = sorted(((ln, round(r, 3)) for ln, r in ratios.items()
                                       if abs(r - 1) > 0.10), key=lambda x: abs(x[1] - 1), reverse=True)
    b, e = a.window
    lt = link_target(a.link_rou, b, e)
    m["link_expected"] = round(lt)
    m["link_finished_ratio"] = m["link_persons"] / lt if lt else 0
    return m


SCALARS = [
    ("car_n", "cars finished", "d"), ("car_mean_dur", "car mean duration s", ".1f"),
    ("car_mean_loss", "car mean timeLoss s", ".1f"), ("bus_n", "bus trips finished", "d"),
    ("rail_n", "train trips finished", "d"), ("teleports", "teleports total", "d"),
    ("teleports_car", "  car", "d"), ("teleports_bus", "  bus", "d"),
    ("teleports_rail", "  rail", "d"), ("bus_wrong_lane", "bus wrong-lane teleports", "d"),
    ("transit_rerouted", "transit rerouted", "d"), ("person_teleports", "person teleports", "d"),
    ("skipped_stops", "skipped stops", "d"), ("bus_boarding_ratio", "bus boardings / ridership", ".3f"),
    ("lines_within_10pct", "lines >=100 riders within 10%", "d"),
    ("link_finished_ratio", "Link riders finished / expected", ".3f"),
    ("right_before_left", "suspicious right_before_left", "d"),
    ("emergency_braking", "emergency braking", "d"), ("errors", "errors in log", "d"),
]
LISTS = [("top_bus_tele_edges", "bus teleport edges"), ("top_car_tele_edges", "car teleport edges"),
         ("top_rbl_junctions", "right_before_left junctions"),
         ("top_skipped_stops", "skipped stops at"), ("lines_outside_10pct", "lines outside 10%")]


def fmt(v, f):
    return format(v, f) if isinstance(v, (int, float)) else str(v)


def run_label(spec):
    d = spec.partition("@")[0] if spec else ""
    return os.path.basename(os.path.normpath(d))[-12:] if d else ""


def report(a_m, a_name, b_m=None, b_name=None):
    w = 34
    a_name, b_name = run_label(a_name), run_label(b_name)
    if b_m is None:
        print("%-*s %12s" % (w, "metric", a_name[-12:]))
    else:
        print("%-*s %12s %12s %10s" % (w, "metric", a_name[-12:], b_name[-12:], "A-B"))
    for k, label, f in SCALARS:
        v = a_m.get(k, 0)
        if k == "lines_within_10pct":
            label += " (of %d)" % a_m.get("lines_checked", 0)
        if b_m is None:
            print("%-*s %12s" % (w, label, fmt(v, f)))
        else:
            bv = b_m.get(k, 0)
            print("%-*s %12s %12s %10s" % (w, label, fmt(v, f), fmt(bv, f), fmt(v - bv, "+" + f)))
    for k, label in LISTS:
        items = a_m.get(k) or []
        if items:
            more = " (+%d more)" % (len(items) - 10) if len(items) > 10 else ""
            print("%s: %s%s" % (label, ", ".join("%s %s" % (x, n) for x, n in items[:10]), more))
    if b_m is not None:
        new = {t: n for t, n in a_m.get("msg_types", {}).items() if t not in b_m.get("msg_types", {})}
        gone = [t for t in b_m.get("msg_types", {}) if t not in a_m.get("msg_types", {})]
        print("new warning/error types in A: %d" % len(new))
        for t, n in sorted(new.items(), key=lambda x: -x[1])[:TOP]:
            print("  %5d  %s" % (n, t))
        if gone:
            print("types only in B: %d" % len(gone))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("run_dir", help="output dir, optionally dir@gtfs_dir")
    p.add_argument("--compare", help="baseline dir[@gtfs_dir]; deltas are run_dir - compare")
    p.add_argument("--json", help="also write run_dir metrics to this JSON file")
    p.add_argument("--gtfs", default=DEF_GTFS, help="dir with bus/ and rail/ gtfs_pt_vehicles.add.xml")
    p.add_argument("--tripinfo", help="tripinfo file name (default: tripinfo_output.xml, else tripinfo.xml)")
    p.add_argument("--log", default="log.xml", help="log file name")
    p.add_argument("--bus-riders", default=DEF_BUS_RIDERS)
    p.add_argument("--link-rou", default=DEF_LINK_ROU)
    p.add_argument("--window", nargs=2, type=float, default=(18000, 43200), metavar=("B", "E"),
                   help="window for Link expected riders (default 18000 43200)")
    a = p.parse_args()
    am = summarize(a.run_dir, a)
    bm = summarize(a.compare, a) if a.compare else None
    report(am, a.run_dir, bm, a.compare)
    if a.json:
        with open(a.json, "w") as f:
            json.dump(am, f, indent=1)


if __name__ == "__main__":
    main()
