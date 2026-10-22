"""Load the scenario settings (Simulation/scenario.json) shared by the GTFS notebook, the rider script, the route
check and the line ranking, so a scenario (bus feed, sim date, ridership period, lines) is set in one place.

    import scenario
    SIM = scenario.load()        # reads $SUMO_SCENARIO if set, else Simulation/scenario.json

Keys from the file: name, bus_feed, sim_date (YYYY-MM-DD), ridership_period, keep_routes,
optional ridership_period_dates [first, last].
Derived: bus_feed_path (absolute), gtfs_date (YYYYMMDD, for gtfs2pt --date), weekday ("wednesday"),
keep_lines (route names as SUMO lines, "C Line" -> "C_Line"), rider_prefix ("kcm_riders_253_AM_MID").
Optional "rail" section (Link): feed, sim_date, lines, ridership_file, ridership_label, ridership_dates,
downtown_stations, time_of_day_share; derived feed_path, gtfs_date, weekday, keep_lines, ridership_path,
rider_prefix ("link_riders_2026-04_05_AM_MID").
"""
import datetime
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
REQUIRED = ["name", "bus_feed", "sim_date", "ridership_period", "keep_routes"]


def load(path=None, verbose=True):
    path = os.path.abspath(path or os.environ.get("SUMO_SCENARIO") or os.path.join(HERE, "scenario.json"))
    with open(path, encoding="utf-8") as f:
        s = json.load(f)
    missing = [k for k in REQUIRED if k not in s]
    if missing:
        raise ValueError(f"{path}: missing {missing}")
    date = datetime.date.fromisoformat(s["sim_date"])
    s["scenario_file"] = path
    s["bus_feed_path"] = os.path.normpath(os.path.join(os.path.dirname(path), s["bus_feed"]))
    s["gtfs_date"] = date.strftime("%Y%m%d")
    s["weekday"] = WEEKDAYS[date.weekday()]
    s["ridership_period"] = str(s["ridership_period"])
    s["keep_lines"] = [r.replace(" ", "_") for r in s["keep_routes"]]
    s["rider_prefix"] = f"kcm_riders_{s['ridership_period']}_AM_MID"

    warnings = []
    if not os.path.exists(s["bus_feed_path"]):
        warnings.append(f"bus_feed not found: {s['bus_feed_path']}")
    if date.weekday() >= 5:
        warnings.append(f"sim_date {date} is a {s['weekday']}; the ridership is weekday ridership")
    if s.get("ridership_period_dates"):
        a, b = (datetime.date.fromisoformat(x) for x in s["ridership_period_dates"])
        if not a <= date <= b:
            warnings.append(f"sim_date {date} is outside ridership period {s['ridership_period']} ({a} to {b})")
    if len(set(s["keep_routes"])) != len(s["keep_routes"]):
        warnings.append("keep_routes has duplicates")

    # Link light rail (optional section)
    r = s.get("rail")
    if r:
        base = os.path.dirname(path)
        rdate = datetime.date.fromisoformat(r["sim_date"])
        r["feed_path"] = os.path.normpath(os.path.join(base, r["feed"]))
        r["gtfs_date"] = rdate.strftime("%Y%m%d")
        r["weekday"] = WEEKDAYS[rdate.weekday()]
        r["keep_lines"] = [l.replace(" ", "_") for l in r["lines"]]
        r["ridership_path"] = os.path.normpath(os.path.join(base, r["ridership_file"]))
        r["rider_prefix"] = f"link_riders_{r['ridership_label']}_AM_MID"
        for k in ("feed_path", "ridership_path"):
            if not os.path.exists(r[k]):
                warnings.append(f"rail {k[:-5]} not found: {r[k]}")
        if rdate.weekday() >= 5:
            warnings.append(f"rail sim_date {rdate} is a {r['weekday']}; the Link ridership is weekday ridership")
        if r.get("ridership_dates"):
            a, b = (datetime.date.fromisoformat(x) for x in r["ridership_dates"])
            if not a <= rdate <= b:
                warnings.append(f"rail sim_date {rdate} is outside the rail ridership dates ({a} to {b})")
    s["warnings"] = warnings
    if verbose:
        print(f"scenario {s['name']}: feed {os.path.basename(s['bus_feed_path'])}, sim date {date} ({s['weekday']}), "
              f"ridership period {s['ridership_period']}, {len(s['keep_routes'])} lines  [{path}]")
        if r:
            print(f"  rail: feed {os.path.basename(r['feed_path'])}, sim date {r['sim_date']} ({r['weekday']}), "
                  f"ridership {r['ridership_label']}, {len(r['downtown_stations'])} downtown stations")
        for w in warnings:
            print("  WARNING:", w)
    return s
