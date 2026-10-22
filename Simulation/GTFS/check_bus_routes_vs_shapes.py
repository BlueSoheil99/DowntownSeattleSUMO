"""Check the SUMO bus routes made by gtfs2pt against the GTFS shapes.

gtfs2pt (without --osm-routes) joins consecutive stops by the shortest path and ignores shapes.txt, so a
bus can take a different street than the real route. This script compares every generated route with the
path-accurate GTFS shape of its trips (the analog of ISE in Kaiser & Schmaus 2026), compares the served
stop sequence with the GTFS one (RNS / RIS), and counts planned vs generated trips per line.

Run from Simulation/GTFS/ (analysis only, nothing in the network or bus files is changed):
    python check_bus_routes_vs_shapes.py
Outputs go to route_check/: route_check_trips.csv, route_check_lines.csv, route_check_summary.md and
one GeoJSON per flagged route pattern (shape vs route).
"""
import bisect
import collections
import io
import json
import os
import sys
import time
import zipfile
import xml.etree.ElementTree as ET

import numpy as np
import pandas as pd
import shapely
from shapely.geometry import LineString
from shapely.ops import substring

SUMO_HOME = os.environ.get("SUMO_HOME", r"C:\Program Files (x86)\SUMO")
sys.path.insert(0, os.path.join(SUMO_HOME, "tools"))
import sumolib  # noqa: E402  (SUMO's own copy, never pip-install it)

# ==============================
# CONFIG
# ==============================
NET_FILE = "soheil_seattle_merged_pedspeed.net.xml"
VEHICLE_FILE = "bus/gtfs_pt_vehicles.add.xml"
STOP_FILE = "bus/gtfs_pt_stops.add.xml"
DOWNTOWN_ZIP = "gtfs data/kcm_google_transit_downtown.zip"   # filtered + snapped feed
FULL_ZIP = "gtfs data/kcm_google_transit.zip"                # unfiltered feed, for planned counts
OUT_DIR = "route_check"

# same lines and bounding box as the filtering cell in seattle_sumo_gtfsData_setup.ipynb
KEEP_ROUTES = ["C Line", "D Line", "E Line", "G Line", "H Line",
               "4", "7", "8", "36", "2", "40", "70", "62", "14", "1", "5", "49", "13", "11", "3", "150", "10",
               "12", "124", "21", "101", "132", "28", "131", "27", "24", "33", "125", "102", "322", "256", "17",
               "57", "56", "113"]
LAT_MIN, LAT_MAX = 47.58, 47.65
LON_MIN, LON_MAX = -122.37, -122.30

DATE = 20260617             # gtfs2pt --date
WEEKDAY = "wednesday"       # weekday of DATE
WINDOW = (5 * 3600, 12 * 3600)

STEP_M = 5.0                # sample spacing along route / shape
OFF_DIST_M = 25.0           # a sample farther than this from the other line is "off"
FLAG_LONGEST_OFF_M = 100.0  # flag: longest continuous off-shape stretch of the route
FLAG_OFF_SHARE = 0.05       # flag: share of the route length that is off the shape
OFFSET_MAX_M = 50.0         # an off stretch that never exceeds this is a geometry offset, not another street
TERMINUS_M = 150.0          # an off stretch entirely within the first/last 2 * TERMINUS_M of the route is a terminus artifact
MOVED_STOP_M = 15.0         # snapping moved a stop by more than this
MOVED_STOP_NEAR_M = 100.0   # off stretch this close to a moved stop -> snapping
MISSING_STREET_R = 15.0     # a shape point with no bus edge within this radius lies on a street missing from the net
STREET_STOP_R = 60.0        # stops within this distance name a stretch (the network has no street names)


def hms(s):
    """'HH:MM:SS' series (hours may exceed 24) -> seconds"""
    p = s.str.split(":", expand=True).astype(float)
    return p[0] * 3600 + p[1] * 60 + p[2]


def read_zip(path, names, usecols=None):
    with zipfile.ZipFile(path) as z:
        return {n: pd.read_csv(io.BytesIO(z.read(n)), dtype=str,
                               usecols=(usecols or {}).get(n), keep_default_na=False) for n in names}


def active_services(cal, cal_dates):
    d = str(DATE)
    on = set(cal[(cal[WEEKDAY] == "1") & (cal.start_date <= d) & (cal.end_date >= d)].service_id)
    day = cal_dates[cal_dates.date == d]
    on |= set(day[day.exception_type == "1"].service_id)
    on -= set(day[day.exception_type == "2"].service_id)
    return on


def stop_id_of(bus_stop):
    """gtfs_<stop_id>[...] -> stop_id"""
    return bus_stop.split("_")[1]


def runs(mask):
    """[(first, last)] index ranges of consecutive True values"""
    out, start = [], None
    for i, m in enumerate(mask):
        if m and start is None:
            start = i
        elif not m and start is not None:
            out.append((start, i - 1))
            start = None
    if start is not None:
        out.append((start, len(mask) - 1))
    return out


def md_table(df):
    """DataFrame -> markdown table (no tabulate dependency)"""
    cols = list(df.columns)
    out = ["| " + " | ".join(map(str, cols)) + " |", "|" + "---|" * len(cols)]
    out += ["| " + " | ".join("" if pd.isna(v) else str(v) for v in row) + " |" for row in df.itertuples(index=False)]
    return "\n".join(out)


def sample(line, step=STEP_M):
    """positions and points every `step` m along line (including the end)"""
    pos = np.append(np.arange(0.0, line.length, step), line.length)
    return pos, shapely.line_interpolate_point(line, pos)


def main():
    t0 = time.time()
    os.makedirs(OUT_DIR, exist_ok=True)

    # ------------------------------
    # GTFS: planned trips in the full feed
    # ------------------------------
    full = read_zip(FULL_ZIP, ["routes.txt", "trips.txt", "stop_times.txt", "stops.txt",
                               "calendar.txt", "calendar_dates.txt"],
                    usecols={"stop_times.txt": ["trip_id", "arrival_time", "stop_id", "stop_sequence"]})
    routes = full["routes.txt"]
    routes = routes[routes.route_short_name.isin(KEEP_ROUTES)].copy()
    routes["line"] = routes.route_short_name.str.replace(" ", "_")
    route_line = dict(zip(routes.route_id, routes.line))
    services = active_services(full["calendar.txt"], full["calendar_dates.txt"])
    ftrips = full["trips.txt"]
    ftrips = ftrips[ftrips.route_id.isin(route_line) & ftrips.service_id.isin(services)].copy()
    ftrips["line"] = ftrips.route_id.map(route_line)

    fstops = full["stops.txt"][["stop_id", "stop_name", "stop_lat", "stop_lon"]].copy()
    fstops[["stop_lat", "stop_lon"]] = fstops[["stop_lat", "stop_lon"]].astype(float)
    fst = full["stop_times.txt"]
    fst = fst[fst.trip_id.isin(ftrips.trip_id)].merge(fstops, on="stop_id")
    fst["t"] = hms(fst.arrival_time)
    fst["seq"] = fst.stop_sequence.astype(int)
    fst["in_bbox"] = fst.stop_lat.between(LAT_MIN, LAT_MAX) & fst.stop_lon.between(LON_MIN, LON_MAX)
    in_win = fst[fst.in_bbox & fst.t.between(*WINDOW)]
    planned = set(in_win.trip_id)
    # stop sequence the filtering cell kept (stops inside the bbox), before snapping
    bbox_seq = (fst[fst.in_bbox].sort_values(["trip_id", "seq"]).groupby("trip_id").stop_id.apply(list).to_dict())

    # ------------------------------
    # GTFS: filtered + snapped feed
    # ------------------------------
    dt = read_zip(DOWNTOWN_ZIP, ["trips.txt", "stop_times.txt", "stops.txt", "shapes.txt"])
    dtrips = dt["trips.txt"].set_index("trip_id")
    dst = dt["stop_times.txt"].copy()
    dst["seq"] = dst.stop_sequence.astype(int)
    dst["dist"] = pd.to_numeric(dst.shape_dist_traveled, errors="coerce")
    dst = dst.sort_values(["trip_id", "seq"])
    dt_seq = dst.groupby("trip_id").stop_id.apply(list).to_dict()
    dt_dist = {(r.trip_id, r.stop_id): r.dist for r in dst.itertuples()}
    dstops = dt["stops.txt"][["stop_id", "stop_lat", "stop_lon"]].copy()
    dstops[["stop_lat", "stop_lon"]] = dstops[["stop_lat", "stop_lon"]].astype(float)

    shapes = dt["shapes.txt"].copy()
    shapes["seq"] = shapes.shape_pt_sequence.astype(int)
    shapes[["lat", "lon"]] = shapes[["shape_pt_lat", "shape_pt_lon"]].astype(float)
    shapes["dist"] = pd.to_numeric(shapes.shape_dist_traveled, errors="coerce")
    shapes = shapes.sort_values(["shape_id", "seq"])

    # ------------------------------
    # SUMO network, stops, routes, vehicles
    # ------------------------------
    print("reading network ...", flush=True)
    net = sumolib.net.readNet(NET_FILE)
    stop_lane = {}
    for bs in ET.parse(STOP_FILE).getroot().iter("busStop"):
        stop_lane[bs.get("id")] = (bs.get("lane"), float(bs.get("startPos")), float(bs.get("endPos")))
    vroot = ET.parse(VEHICLE_FILE).getroot()
    sumo_routes = {r.get("id"): (r.get("edges").split(), [s.get("busStop") for s in r.findall("stop")])
                   for r in vroot.iter("route")}
    vehicles = pd.DataFrame([{"trip_id": v.get("id").rsplit(".", 1)[0], "route": v.get("route"),
                              "depart": float(v.get("depart")), "line": v.get("line")}
                             for v in vroot.iter("vehicle")])
    vehicles["in_window"] = vehicles.depart.between(*WINDOW)
    generated = set(vehicles[vehicles.in_window].trip_id)

    # moved stops (snapping) in net XY
    mv = fstops.merge(dstops, on="stop_id", suffixes=("_o", "_n"))
    moved_xy = {}
    for r in mv.itertuples():
        xo, yo = net.convertLonLat2XY(r.stop_lon_o, r.stop_lat_o)
        xn, yn = net.convertLonLat2XY(r.stop_lon_n, r.stop_lat_n)
        if np.hypot(xo - xn, yo - yn) > MOVED_STOP_M:
            moved_xy[r.stop_id] = (xn, yn)

    # ------------------------------
    # geometry helpers
    # ------------------------------
    lane_cache = {}

    def edge_lane(eid):
        if eid not in lane_cache:
            e = net.getEdge(eid)
            lane = next((ln for ln in e.getLanes() if ln.allows("bus")), e.getLanes()[0])
            lane_cache[eid] = lane
        return lane_cache[eid]

    # The networks carry no street names (netconvert ran without --output.street-names), so stretches are
    # named after the KCM stops along them: "1st Ave S & S Atlantic St" -> 1st Ave S, S Atlantic St.
    all_stop_xy = [net.convertLonLat2XY(lon, lat) for lon, lat in zip(fstops.stop_lon, fstops.stop_lat)]
    stop_tree = shapely.STRtree(shapely.points(all_stop_xy))
    stop_names = fstops.stop_name.to_numpy()

    def nearby_streets(points):
        """most frequent street names of the KCM stops within STREET_STOP_R of the points"""
        pts = points[::4] if len(points) > 4 else points            # every ~20 m
        idx, dist = stop_tree.query_nearest(pts, max_distance=STREET_STOP_R, return_distance=True)
        count = collections.Counter()
        for i in idx[1]:
            for part in stop_names[i].replace(" / ", " & ").split("&"):
                part = part.strip()
                if part and not part.lower().startswith(("bay ", "stop ")):
                    count[part] += 1
        if not count:
            x, y = shapely.get_coordinates(points)[len(points) // 2]
            lon, lat = net.convertXY2LonLat(x, y)
            return f"({lat:.5f},{lon:.5f})"
        top = count.most_common(3)
        return ", ".join(f"{s} ({n})" for s, n in top if n >= max(2, top[0][1] // 4)) or top[0][0]

    def stretch_label(edges_in_stretch, points):
        named = [net.getEdge(e).getName() for e in edges_in_stretch if net.getEdge(e).getName()]
        return " | ".join(dict.fromkeys(named)) if named else nearby_streets(points)

    def route_geometry(edges, stops):
        """route polyline (bus lanes), edge start offsets, and positions of the served stops along it"""
        pts, starts = [], []
        for eid in edges:
            shp = edge_lane(eid).getShape()
            if pts and np.hypot(pts[-1][0] - shp[0][0], pts[-1][1] - shp[0][1]) < 1e-6:
                shp = shp[1:]
            starts.append(LineString(pts + [shp[0]]).length if len(pts) >= 1 else 0.0)
            pts.extend(shp)
        line = LineString(pts)
        positions, i = [], 0
        for bs in stops:
            lane_id, sp, ep = stop_lane[bs]
            eid = lane_id.rsplit("_", 1)[0]
            try:
                i = edges.index(eid, i)
            except ValueError:
                positions.append(None)
                continue
            lane = edge_lane(eid)
            scale = LineString(lane.getShape()).length / lane.getLength()
            positions.append((starts[i] + sp * scale, starts[i] + ep * scale))
        return line, starts, positions

    def shape_line(shape_id):
        s = shapes[shapes.shape_id == shape_id]
        xy = [net.convertLonLat2XY(lon, lat) for lon, lat in zip(s.lon, s.lat)]
        line = LineString(xy)
        cum = np.concatenate([[0.0], np.cumsum(np.hypot(*np.diff(np.array(xy), axis=0).T))])
        return line, s.dist.to_numpy(), cum

    shape_cache = {}

    def bearing(p, q):
        return np.degrees(np.arctan2(q[0] - p[0], q[1] - p[1])) % 360

    def has_bus_edge(x, y, heading):
        """a bus edge within MISSING_STREET_R running within 45 deg of `heading` (so the opposite
        carriageway of a one-way pair does not count)"""
        for e, _ in net.getNeighboringEdges(x, y, MISSING_STREET_R):
            if not e.allows("bus"):
                continue
            shp = e.getShape()
            seg = min(zip(shp, shp[1:]), key=lambda s: shapely.distance(LineString(s), shapely.Point(x, y)))
            if abs((bearing(*seg) - heading + 180) % 360 - 180) < 45:
                return True
        return False

    # ------------------------------
    # metrics per route pattern (sumo route, shape)
    # ------------------------------
    win = vehicles[vehicles.in_window].copy()
    win["shape_id"] = win.trip_id.map(dtrips.shape_id)
    win["direction_id"] = win.trip_id.map(dtrips.direction_id)
    win["headsign"] = win.trip_id.map(dtrips.trip_headsign)
    patterns = {}
    geojson_dir = os.path.join(OUT_DIR, "flagged_geojson")
    os.makedirs(geojson_dir, exist_ok=True)
    print(f"checking {win.groupby(['route', 'shape_id']).ngroups} route patterns ...", flush=True)
    for (rid, shape_id), grp in win.groupby(["route", "shape_id"]):
        edges, stops = sumo_routes[rid]
        rline, starts, spos = route_geometry(edges, stops)
        served = [(bs, p) for bs, p in zip(stops, spos) if p is not None]
        res = {"n_route_stops": len(stops), "stops_not_on_route": len(stops) - len(served)}
        if len(served) < 2:
            res["note"] = "fewer than 2 stops located on route"
            patterns[(rid, shape_id)] = res
            continue
        a, b = served[0][1][0], served[-1][1][1]
        rclip = substring(rline, a, b)

        if shape_id not in shape_cache:
            shape_cache[shape_id] = shape_line(shape_id)
        sline, sdist, scum = shape_cache[shape_id]
        tid = grp.trip_id.iloc[0]
        d0 = dt_dist.get((tid, stop_id_of(served[0][0])))
        d1 = dt_dist.get((tid, stop_id_of(served[-1][0])))
        if d0 is None or d1 is None or np.isnan(d0) or np.isnan(d1) or np.isnan(sdist).any():
            sclip, res["note"] = sline, "shape not clipped (no shape_dist_traveled)"
        else:
            sclip = substring(sline, float(np.interp(d0, sdist, scum)), float(np.interp(d1, sdist, scum)))

        # route -> shape
        rpos, rpts = sample(rclip)
        rd = shapely.distance(rpts, sclip)
        off = rd > OFF_DIST_M
        off_runs = runs(off)
        longest = max(off_runs, key=lambda r: rpos[r[1]] - rpos[r[0]], default=None)
        longest_m = (rpos[longest[1]] - rpos[longest[0]] + STEP_M) if longest else 0.0
        streets, off_edges, off_mid = "", [], ""
        if longest:
            for p in rpos[longest[0]:longest[1] + 1]:
                eid = edges[bisect.bisect_right(starts, p + a) - 1]
                if eid not in off_edges:
                    off_edges.append(eid)
            streets = stretch_label(off_edges, rpts[longest[0]:longest[1] + 1])
            mx, my = shapely.get_coordinates(rpts[(longest[0] + longest[1]) // 2])[0]
            mlon, mlat = net.convertXY2LonLat(mx, my)
            off_mid = f"{mlat:.5f},{mlon:.5f}"
        # shape -> route
        spos_, spts = sample(sclip)
        sd = shapely.distance(spts, rclip)
        soff = sd > OFF_DIST_M
        s_runs = runs(soff)
        s_longest = max(s_runs, key=lambda r: spos_[r[1]] - spos_[r[0]], default=None)
        s_longest_m = (spos_[s_longest[1]] - spos_[s_longest[0]] + STEP_M) if s_longest else 0.0
        shape_streets = nearby_streets(spts[s_longest[0]:s_longest[1] + 1]) if s_longest else ""

        flagged = longest_m > FLAG_LONGEST_OFF_M or off.mean() > FLAG_OFF_SHARE
        cause = ""
        if flagged:
            causes = []
            # geometry offset: the off stretch never gets farther than OFFSET_MAX_M from the shape, i.e. the
            # same street drawn differently (e.g. the rebuilt Alaskan Way), not a different street
            if longest and rd[longest[0]:longest[1] + 1].max() < OFFSET_MAX_M:
                causes.append(f"geometry offset (max {rd[longest[0]:longest[1] + 1].max():.0f} m from shape)")
            # terminus artifact: the longest off stretch lies entirely within the first/last 2*TERMINUS_M
            if longest and (rpos[longest[1]] < 2 * TERMINUS_M or rpos[longest[0]] > rclip.length - 2 * TERMINUS_M):
                causes.append("terminus")
            # missing street: along the shape's off stretch there is no bus edge in the shape's direction
            if s_longest:
                xy = shapely.get_coordinates(spts[s_longest[0]:s_longest[1] + 1])
                checks = [not has_bus_edge(*xy[i], bearing(xy[max(i - 1, 0)], xy[min(i + 1, len(xy) - 1)]))
                          for i in range(0, len(xy), 4)]
                share_no_edge = np.mean(checks)
                if share_no_edge > 0.5:
                    causes.append(f"no bus edge in travel direction along shape ({share_no_edge:.0%} of off-shape points)")
            # snapping: a stop moved by snapping, near the off stretch, now lies off the shape (if the moved
            # stop is still on the shape, snapping placed it correctly and the route itself is the problem)
            if longest:
                seg = substring(rclip, rpos[longest[0]], rpos[longest[1]])
                near = [s for s, _ in served if stop_id_of(s) in moved_xy and
                        shapely.distance(shapely.Point(moved_xy[stop_id_of(s)]), seg) < MOVED_STOP_NEAR_M and
                        shapely.distance(shapely.Point(moved_xy[stop_id_of(s)]), sclip) > OFFSET_MAX_M]
                if near:
                    causes.append("near stop moved by snapping (" + " ".join(stop_id_of(s) for s in near) + ")")
            cause = "; ".join(causes) or "shortest path instead of shape"
            gj = {"type": "FeatureCollection", "features": []}
            for kind, ln in (("shape", sclip), ("route", rclip)):
                coords = [list(net.convertXY2LonLat(x, y)) for x, y in ln.coords]
                gj["features"].append({"type": "Feature", "properties": {"kind": kind, "route": rid,
                                                                          "shape_id": shape_id},
                                       "geometry": {"type": "LineString", "coordinates": coords}})
            line_name = grp.line.iloc[0]
            with open(os.path.join(geojson_dir, f"{line_name}_{rid}_{shape_id}.geojson"), "w") as f:
                json.dump(gj, f)

        res.update({
            "route_len_m": rclip.length, "shape_len_m": sclip.length,
            "len_ratio": rclip.length / sclip.length if sclip.length else np.nan,
            "off_share": off.mean(), "longest_off_m": longest_m, "longest_off_streets": streets,
            "longest_off_mid_latlon": off_mid,
            "longest_off_maxdist_m": rd[longest[0]:longest[1] + 1].max() if longest else 0.0,
            "longest_off_edges": f"{off_edges[0]} .. {off_edges[-1]} ({len(off_edges)})" if off_edges else "",
            "hd_route_to_shape_m": rd.max(), "p95_route_to_shape_m": np.percentile(rd, 95),
            "hd_shape_to_route_m": sd.max(), "p95_shape_to_route_m": np.percentile(sd, 95),
            "shape_longest_off_m": s_longest_m, "shape_off_streets": shape_streets,
            "flagged": flagged, "cause": cause,
        })
        patterns[(rid, shape_id)] = res

    # ------------------------------
    # per trip: metrics + stop sequences
    # ------------------------------
    rows = []
    for r in win.itertuples():
        res = patterns.get((r.route, r.shape_id), {})
        gtfs_seq = dt_seq.get(r.trip_id, [])
        sumo_seq = [stop_id_of(s) for s in sumo_routes[r.route][1]]
        rns = len(sumo_seq) / len(gtfs_seq) if gtfs_seq else np.nan
        ris = (sum(x == y for x, y in zip(sumo_seq, gtfs_seq)) / len(gtfs_seq)) if rns == 1 else 0.0
        bseq = bbox_seq.get(r.trip_id, [])
        rows.append({
            "trip_id": r.trip_id, "line": r.line, "direction_id": r.direction_id, "headsign": r.headsign,
            "sumo_route": r.route, "shape_id": r.shape_id, "depart": r.depart,
            "n_gtfs_stops": len(gtfs_seq), "n_sumo_stops": len(sumo_seq), "RNS": rns, "RIS": ris,
            "dropped_by_snapping": " ".join(s for s in bseq if s not in gtfs_seq),
            "dropped_by_gtfs2pt": " ".join(s for s in gtfs_seq if s not in sumo_seq),
            "extra_in_sumo": " ".join(s for s in sumo_seq if s not in gtfs_seq),
            **res,
        })
    trips_df = pd.DataFrame(rows)
    trips_df.round(3).to_csv(os.path.join(OUT_DIR, "route_check_trips.csv"), index=False)

    # ------------------------------
    # trip counts per line + missing-trip reasons
    # ------------------------------
    trip_line = dict(zip(ftrips.trip_id, ftrips.line))
    veh_by_trip = vehicles.set_index("trip_id")
    reasons = {}
    for t in planned - generated:
        seq = dt_seq.get(t, [])
        if t not in dtrips.index or len(seq) < 2:
            reasons[t] = "lt2_stops_in_network"
        elif t in veh_by_trip.index and not veh_by_trip.loc[t, "in_window"]:
            reasons[t] = "no_in_area_stop_in_window"
        elif t not in veh_by_trip.index:
            reasons[t] = "other_no_vehicle"
        else:
            reasons[t] = "other"
    extra = generated - planned

    lines = []
    for line in [r.replace(" ", "_") for r in KEEP_ROUTES]:
        pl = {t for t in planned if trip_line.get(t) == line}
        tl = trips_df[trips_df.line == line]
        rs = collections.Counter(reasons[t] for t in pl if t in reasons)
        worst = tl.loc[tl.longest_off_m.idxmax()] if len(tl) and tl.longest_off_m.notna().any() else None
        lines.append({
            "line": line, "planned": len(pl), "downtown": len(pl & set(dtrips.index)),
            "generated": int((vehicles.in_window & (vehicles.line == line)).sum()),
            "delta": int((vehicles.in_window & (vehicles.line == line)).sum()) - len(pl),
            "missing_lt2_stops": rs["lt2_stops_in_network"], "missing_window": rs["no_in_area_stop_in_window"],
            "missing_other": rs["other_no_vehicle"] + rs["other"],
            "extra_generated": sum(trip_line.get(t, vehicles.set_index('trip_id').line.get(t)) == line
                                   for t in extra),
            "trips_checked": len(tl), "trips_flagged": int(tl.flagged.fillna(False).sum()),
            "match_ratio": 1 - tl.flagged.fillna(False).mean() if len(tl) else np.nan,
            "mean_off_share": tl.off_share.mean(), "max_off_share": tl.off_share.max(),
            "worst_longest_off_m": worst.longest_off_m if worst is not None else np.nan,
            "worst_streets": worst.longest_off_streets if worst is not None else "",
        })
    lines_df = pd.DataFrame(lines)
    lines_df["flagged_share"] = lines_df.trips_flagged / lines_df.trips_checked
    lines_df = lines_df.sort_values(["flagged_share", "line"], ascending=[False, True])
    lines_df.round(3).to_csv(os.path.join(OUT_DIR, "route_check_lines.csv"), index=False)

    # ------------------------------
    # flagged patterns + summary
    # ------------------------------
    fl = trips_df[trips_df.flagged.fillna(False)]
    pat = (fl.groupby(["line", "direction_id", "headsign", "sumo_route", "shape_id"])
           .agg(trips=("trip_id", "size"), longest_off_m=("longest_off_m", "first"),
                off_share=("off_share", "first"), maxdist=("longest_off_maxdist_m", "first"),
                shape_longest_off_m=("shape_longest_off_m", "first"),
                streets=("longest_off_streets", "first"), shape_streets=("shape_off_streets", "first"),
                mid=("longest_off_mid_latlon", "first"), cause=("cause", "first"))
           .reset_index().sort_values(["line", "longest_off_m"], ascending=[True, False]))
    pat.round(3).to_csv(os.path.join(OUT_DIR, "route_check_flagged_patterns.csv"), index=False)

    ris_lt1 = trips_df[trips_df.RIS < 1]
    n_chk, n_fl = len(trips_df), int(trips_df.flagged.fillna(False).sum())
    artifact = fl.cause.str.startswith(("geometry offset", "terminus"))
    n_art = int(artifact.sum())
    n_snap_drop = int(trips_df.dropped_by_snapping.astype(bool).sum())
    md = [
        "# Bus route check vs GTFS shapes",
        "",
        f"Date {DATE}, window {WINDOW[0]}-{WINDOW[1]} s. Thresholds: off = sample > {OFF_DIST_M:g} m from the "
        f"shape (every {STEP_M:g} m); flag = longest off stretch > {FLAG_LONGEST_OFF_M:g} m or off share > "
        f"{FLAG_OFF_SHARE:.0%}.",
        "",
        f"- trips checked: {n_chk}, flagged: {n_fl}, match ratio: {1 - n_fl / n_chk:.3f}",
        f"- of the flagged trips, {n_art} are artifacts (geometry offset / terminus) and {n_fl - n_art} real "
        f"deviations; match ratio without artifacts: {1 - (n_fl - n_art) / n_chk:.3f}",
        f"- trips with stops dropped by snapping (in the bbox but outside the network, expected): {n_snap_drop}",
        f"- route patterns checked: {len(patterns)}, flagged: {len(pat)}",
        f"- planned trips: {len(planned)}, generated in window: {len(generated)}, "
        f"missing: {len(planned - generated)} ({dict(collections.Counter(reasons.values()))}), "
        f"generated but not planned: {len(extra)}",
        f"- trips with RIS < 1: {len(ris_lt1)} (RNS != 1: {int((ris_lt1.RNS != 1).sum())})",
        f"- runtime: {time.time() - t0:.0f} s",
        "",
        "## Flagged route patterns",
        "",
        md_table(pat.round(1)) if len(pat) else "none",
        "",
        "## Lines",
        "",
        md_table(lines_df.round(3)),
    ]
    with open(os.path.join(OUT_DIR, "route_check_summary.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")
    print("\n".join(md[:9]))
    print(f"outputs in {OUT_DIR}/")


if __name__ == "__main__":
    main()
