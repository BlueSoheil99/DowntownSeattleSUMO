"""Load the scenario settings (Simulation/scenario.json) shared by the GTFS notebook, the rider script, the route
check and the line ranking, so a scenario (bus feed, sim date, ridership period, lines) is set in one place.

    import scenario
    SIM = scenario.load()        # reads $SUMO_SCENARIO if set, else Simulation/scenario.json

Keys from the file: name, bus_feed, sim_date (YYYY-MM-DD), ridership_period, keep_routes,
optional ridership_period_dates [first, last].
Derived: bus_feed_path (absolute), gtfs_date (YYYYMMDD, for gtfs2pt --date), weekday ("wednesday"),
keep_lines (route names as SUMO lines, "C Line" -> "C_Line"), rider_prefix ("kcm_riders_253_AM_MID").
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
    s["warnings"] = warnings
    if verbose:
        print(f"scenario {s['name']}: feed {os.path.basename(s['bus_feed_path'])}, sim date {date} ({s['weekday']}), "
              f"ridership period {s['ridership_period']}, {len(s['keep_routes'])} lines  [{path}]")
        for w in warnings:
            print("  WARNING:", w)
    return s
