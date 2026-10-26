"""Reroute gtfs2pt bus routes along the GTFS shapes.

gtfs2pt joins consecutive stops by the shortest path, so where a bus passes no stop between two streets it can
take a parallel street (route check: 108 trips, 4 places). This step keeps every stop and replaces only the
stop-to-stop legs that leave the trip's GTFS shape: each leg is re-routed with a Dijkstra over bus-permitted
connections where an edge costs length x (1 + OFF_WEIGHT) if it lies more than OFF_DIST m from the shape.
A leg is replaced only if the new one is at least MIN_GAIN m less off the shape.

Run from Simulation/GTFS after the bus gtfs2pt cell and before the vType cells:
    python route_buses_by_shape.py
Reads soheil_seattle_merged_pedspeed.net.xml, gtfs data/kcm_google_transit_downtown.zip (trips, shapes),
bus/gtfs_pt_stops.add.xml; rewrites route edges in bus/gtfs_pt_vehicles.add.xml (everything else unchanged).
Standard library + sumolib only (no pyproj: UTM projection below).
"""
import collections
import csv
import heapq
import io
import math
import os
import re
import sys
import zipfile

sys.path.insert(0, os.path.join(os.environ.get("SUMO_HOME", r"C:\Program Files (x86)\SUMO"), "tools"))
import sumolib  # noqa: E402

NET = "soheil_seattle_merged_pedspeed.net.xml"
GTFS = "gtfs data/kcm_google_transit_downtown.zip"
STOPS = "bus/gtfs_pt_stops.add.xml"
VEHICLES = "bus/gtfs_pt_vehicles.add.xml"
OFF_DIST = 20.0      # m: an edge further than this from the shape (mean of samples) is "off"
OFF_WEIGHT = 20.0    # off edges cost (1 + OFF_WEIGHT) x their length
MIN_GAIN = 150.0     # m: replace a leg only if it gets at least this much less off-shape length.
                     # 30 m also changed 7, G, 10, 11, 12 (gains 70-109 m, never flagged by the route check);
                     # the lab run S1 showed more teleports/skipped stops there. Real fixes gain 243-1075 m.
SAMPLE = 10.0        # m between samples along an edge
GRID = 50.0          # m cell size of the shape segment index


# ---------- UTM (WGS84) forward projection, Krueger series; matches the net's +proj=utm ----------
def utm_xy(lon, lat, zone):
    a, f, k0 = 6378137.0, 1 / 298.257223563, 0.9996
    n = f / (2 - f)
    A = a / (1 + n) * (1 + n ** 2 / 4 + n ** 4 / 64)
    al = [n / 2 - 2 * n ** 2 / 3 + 5 * n ** 3 / 16, 13 * n ** 2 / 48 - 3 * n ** 3 / 5, 61 * n ** 3 / 240]
    lam0 = math.radians(zone * 6 - 183)
    phi, lam = math.radians(lat), math.radians(lon)
    e2 = 2 * math.sqrt(n) / (1 + n)
    t = math.sinh(math.atanh(math.sin(phi)) - e2 * math.atanh(e2 * math.sin(phi)))
    xi = math.atan2(t, math.cos(lam - lam0))
    eta = math.atanh(math.sin(lam - lam0) / math.sqrt(1 + t * t))
    E = 500000 + k0 * A * (eta + sum(al[j] * math.cos(2 * (j + 1) * xi) * math.sinh(2 * (j + 1) * eta) for j in range(3)))
    N = k0 * A * (xi + sum(al[j] * math.sin(2 * (j + 1) * xi) * math.cosh(2 * (j + 1) * eta) for j in range(3)))
    return E, N


def net_projection(net_file):
    with open(net_file, encoding="utf-8") as f:
        head = f.read(20000)
    m = re.search(r'<location netOffset="([-\d.]+),([-\d.]+)".*?projParameter="([^"]+)"', head, re.S)
    ox, oy, proj = float(m.group(1)), float(m.group(2)), m.group(3)
    zone = int(re.search(r"\+zone=(\d+)", proj).group(1))
    assert "+proj=utm" in proj and "+south" not in proj, proj
    return lambda lon, lat: tuple(v + o for v, o in zip(utm_xy(lon, lat, zone), (ox, oy)))


# ---------- geometry ----------
def seg_dist(p, a, b):
    ax, ay = a
    dx, dy = b[0] - ax, b[1] - ay
    L = dx * dx + dy * dy
    t = 0.0 if L == 0 else max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / L))
    return math.hypot(p[0] - ax - t * dx, p[1] - ay - t * dy)


class ShapeIndex:
    def __init__(self, pts):
        self.segs = list(zip(pts, pts[1:]))
        self.grid = collections.defaultdict(list)
        for i, (a, b) in enumerate(self.segs):
            for gx in range(int(min(a[0], b[0]) // GRID) - 1, int(max(a[0], b[0]) // GRID) + 2):
                for gy in range(int(min(a[1], b[1]) // GRID) - 1, int(max(a[1], b[1]) // GRID) + 2):
                    self.grid[(gx, gy)].append(i)

    def dist(self, p):
        cand = self.grid.get((int(p[0] // GRID), int(p[1] // GRID)))
        if not cand:
            return 999.0
        return min(seg_dist(p, *self.segs[i]) for i in cand)


def samples(shape):
    out = [shape[0]]
    for a, b in zip(shape, shape[1:]):
        L = math.dist(a, b)
        k = max(1, int(L // SAMPLE))
        out += [(a[0] + (b[0] - a[0]) * j / k, a[1] + (b[1] - a[1]) * j / k) for j in range(1, k + 1)]
    return out


# ---------- data ----------
def read_csv(zf, name):
    return list(csv.DictReader(io.TextIOWrapper(zf.open(name), "utf-8-sig")))


def main():
    net = sumolib.net.readNet(NET)
    to_xy = net_projection(NET)
    zf = zipfile.ZipFile(GTFS)
    trip_shape = {r["trip_id"]: r["shape_id"] for r in read_csv(zf, "trips.txt")}
    pts = collections.defaultdict(list)
    for r in read_csv(zf, "shapes.txt"):
        pts[r["shape_id"]].append((int(r["shape_pt_sequence"]), float(r["shape_pt_lon"]), float(r["shape_pt_lat"])))
    shape_xy = {s: [to_xy(lon, lat) for _, lon, lat in sorted(v)] for s, v in pts.items()}

    stop_edge = {m.group(1): m.group(2).rsplit("_", 1)[0]
                 for m in re.finditer(r'<busStop id="([^"]+)"[^>]*lane="([^"]+)"', open(STOPS, encoding="utf-8").read())}
    text = open(VEHICLES, encoding="utf-8").read()
    routes = {}
    for m in re.finditer(r'<route id="([^"]+)" edges="([^"]+)"[^>]*>(.*?)</route>', text, re.S):
        routes[m.group(1)] = (m.group(2).split(), re.findall(r'busStop="([^"]+)"', m.group(3)))
    route_shapes = collections.defaultdict(collections.Counter)
    route_line = {}
    for m in re.finditer(r'<vehicle id="([^"]+)" route="([^"]+)"[^>]*line="([^"]+)"', text):
        sid = trip_shape.get(m.group(1).rsplit(".", 1)[0])
        if sid:
            route_shapes[m.group(2)][sid] += 1
        route_line[m.group(2)] = m.group(3)

    bus_lane = {}

    def lane_shape(e):
        if e not in bus_lane:
            ln = next((l for l in e.getLanes() if l.allows("bus")), None)
            bus_lane[e] = ln.getShape() if ln else e.getShape()
        return bus_lane[e]

    dist_cache = {}

    def edge_off(e, sid, idx):
        k = (e.getID(), sid)
        if k not in dist_cache:
            s = samples(lane_shape(e))
            dist_cache[k] = sum(idx.dist(p) for p in s) / len(s) > OFF_DIST
        return dist_cache[k]

    def bus_succ(e):
        for t, conns in e.getOutgoing().items():
            if t.allows("bus") and any(c.getFromLane().allows("bus") and c.getToLane().allows("bus") for c in conns):
                yield t

    def cost(e, sid, idx):
        return e.getLength() * (1 + OFF_WEIGHT * edge_off(e, sid, idx))

    def off_len(edges, sid, idx):
        return sum(net.getEdge(x).getLength() for x in edges if edge_off(net.getEdge(x), sid, idx))

    def dijkstra(src, dst, sid, idx):
        if src == dst:
            return [src.getID()]
        best = {src: 0.0}
        prev = {}
        pq = [(0.0, 0, src)]
        cnt = 1
        while pq:
            c, _, e = heapq.heappop(pq)
            if e == dst:
                path = [e]
                while path[-1] in prev:
                    path.append(prev[path[-1]])
                return [x.getID() for x in reversed(path)]
            if c > best.get(e, math.inf):
                continue
            for t in bus_succ(e):
                nc = c + cost(t, sid, idx)
                if nc < best.get(t, math.inf):
                    best[t], prev[t] = nc, e
                    heapq.heappush(pq, (nc, cnt, t))
                    cnt += 1
        return None

    new_edges, report = {}, []
    for rid, (edges, stops) in routes.items():
        if not route_shapes.get(rid):
            continue
        sid = route_shapes[rid].most_common(1)[0][0]
        if sid not in shape_xy:
            continue
        idx = ShapeIndex(shape_xy[sid])
        # waypoints: route start, each stop edge in route order, route end -> positions in `edges`
        way, pos = [0], 0
        for s in stops:
            e = stop_edge.get(s)
            if e is None:
                continue
            try:
                pos = edges.index(e, pos)
            except ValueError:
                way = None
                break
            way.append(pos)
        if way is None:
            report.append((rid, "skip: stop edge not in route"))
            continue
        way.append(len(edges) - 1)
        out, changed = [edges[0]], 0
        for i, j in zip(way, way[1:]):
            old = edges[i:j + 1]
            new = old
            if j > i:
                cand = dijkstra(net.getEdge(edges[i]), net.getEdge(edges[j]), sid, idx)
                if cand and cand != old and off_len(cand, sid, idx) <= off_len(old, sid, idx) - MIN_GAIN:
                    new, changed = cand, changed + 1
            out += new[1:]
        if changed:
            new_edges[rid] = out
            report.append((rid, f"{route_line.get(rid)} shape {sid}: {changed} leg(s), off {off_len(edges, sid, idx):.0f} -> {off_len(out, sid, idx):.0f} m"))

    # validate connectivity before writing
    for rid, out in new_edges.items():
        for a, b in zip(out, out[1:]):
            assert net.getEdge(b) in set(bus_succ(net.getEdge(a))), (rid, a, b)

    def repl(m):
        rid = m.group(1)
        return m.group(0) if rid not in new_edges else f'<route id="{rid}" edges="{" ".join(new_edges[rid])}"'
    text2 = re.sub(r'<route id="([^"]+)" edges="[^"]+"', repl, text)
    with open(VEHICLES, "w", encoding="utf-8") as f:
        f.write(text2)
    trips = collections.Counter(route_line[r] for r in new_edges for _ in range(sum(route_shapes[r].values())))
    print(f"route_buses_by_shape: {len(new_edges)} of {len(routes)} routes rerouted along the GTFS shape; trips by line: {dict(trips)}")
    for r in report:
        print("  ", *r)


if __name__ == "__main__":
    main()
