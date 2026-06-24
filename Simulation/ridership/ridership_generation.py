import pandas as pd
import xml.etree.ElementTree as ET
from xml.dom import minidom
from collections import defaultdict

# Inputs
ridership_file = r"E:\SUMO_proj\seattleTransitRidership\kcm_ridership_matched_sumo_stops_253_AM.csv"
route_file = "new_bus_link_route_with_line.rou.xml"
output_person_file = "kcm_personflows_253_AM_with_alighting.rou.xml"

begin_time = 5 * 3600
end_time = 9 * 3600
duration_hours = 4

ridership = pd.read_csv(ridership_file)

ridership["stopId"] = ridership["stopId"].astype(str)
ridership["routeNum"] = ridership["routeNum"].astype(str)

def normalize_route(route):
    route = str(route)
    if route in ["C", "D", "E", "H", "G"]:
        return f"{route}_Line"
    return route

ridership["sumo_line"] = ridership["routeNum"].apply(normalize_route)

for col in ["tripBoardings", "tripAlightings", "departingLoad"]:
    if col in ridership.columns:
        ridership[col] = pd.to_numeric(ridership[col], errors="coerce").fillna(0)

tree = ET.parse(route_file)
root = tree.getroot()

line_to_stop_sequences = defaultdict(list)

for trip in root.findall("trip"):
    if trip.get("type") != "bus":
        continue

    line = trip.get("line")
    if line is None:
        continue

    stops = [s.get("busStop") for s in trip.findall("stop") if s.get("busStop")]

    if len(stops) >= 2:
        line_to_stop_sequences[line].append(stops)

def get_representative_sequence(line):
    sequences = line_to_stop_sequences.get(line, [])
    if not sequences:
        return []
    return max(sequences, key=len)

routes_root = ET.Element("routes")
created = 0
skipped = []
initial_load_records = []

for line, line_df in ridership.groupby("sumo_line"):

    stop_sequence = get_representative_sequence(line)

    if not stop_sequence:
        skipped.append((line, "", "no SUMO stop sequence found"))
        continue

    line_df = line_df[line_df["stopId"].isin(stop_sequence)].copy()

    if line_df.empty:
        continue

    stop_order = {stop: i for i, stop in enumerate(stop_sequence)}
    line_df["stop_order"] = line_df["stopId"].map(stop_order)
    line_df = line_df.sort_values("stop_order")

    # Estimate initial onboard passengers entering the SUMO region
    cum_board = line_df["tripBoardings"].cumsum()
    cum_alight = line_df["tripAlightings"].cumsum()
    initial_load = max(0, (cum_alight - cum_board).max())

    initial_load_records.append({
        "line": line,
        "estimated_initial_load": initial_load,
        "total_boardings": line_df["tripBoardings"].sum(),
        "total_alightings": line_df["tripAlightings"].sum()
    })

    # Destination assignment using downstream alighting weights
    for _, row in line_df.iterrows():
        origin_stop = row["stopId"]
        boardings = row["tripBoardings"]

        if boardings <= 0:
            continue

        origin_idx = stop_order[origin_stop]

        downstream_df = line_df[line_df["stop_order"] > origin_idx].copy()
        downstream_df = downstream_df[downstream_df["tripAlightings"] > 0]

        if downstream_df.empty:
            # fallback: send to last downstream stop
            downstream_stops = [s for s in stop_sequence if stop_order[s] > origin_idx]
            if not downstream_stops:
                skipped.append((line, origin_stop, "no downstream destination"))
                continue

            destination_stop = downstream_stops[-1]
            persons_per_hour = boardings / duration_hours

            pf = ET.SubElement(routes_root, "personFlow", {
                "id": f"pf_{line}_{origin_stop}_{destination_stop}_AM_{created}",
                "begin": str(begin_time),
                "end": str(end_time),
                "personsPerHour": f"{persons_per_hour:.4f}"
            })

            ET.SubElement(pf, "ride", {
                "from": origin_stop,
                "busStop": destination_stop,
                "lines": line
            })

            created += 1
            continue

        total_downstream_alight = downstream_df["tripAlightings"].sum()

        for _, dest_row in downstream_df.iterrows():
            destination_stop = dest_row["stopId"]
            alight_weight = dest_row["tripAlightings"] / total_downstream_alight

            assigned_boardings = boardings * alight_weight
            persons_per_hour = assigned_boardings / duration_hours

            if persons_per_hour <= 0:
                continue

            pf = ET.SubElement(routes_root, "personFlow", {
                "id": f"pf_{line}_{origin_stop}_{destination_stop}_AM_{created}",
                "begin": str(begin_time),
                "end": str(end_time),
                "personsPerHour": f"{persons_per_hour:.4f}"
            })

            ET.SubElement(pf, "ride", {
                "from": origin_stop,
                "busStop": destination_stop,
                "lines": line
            })

            created += 1

xml_str = ET.tostring(routes_root, encoding="utf-8")
pretty_xml = minidom.parseString(xml_str).toprettyxml(indent="    ")

with open(output_person_file, "w", encoding="utf-8") as f:
    f.write(pretty_xml)

pd.DataFrame(skipped, columns=["line", "stopId", "reason"]).to_csv(
    "skipped_personflows_253_AM_with_alighting.csv", index=False
)

pd.DataFrame(initial_load_records).to_csv(
    "../clean corrected inputs/estimated_initial_load_by_line_253_AM.csv", index=False
)

print(f"Generated: {output_person_file}")
print(f"Person flows created: {created}")
print(f"Skipped rows: {len(skipped)}")
print("Saved estimated initial loads to: estimated_initial_load_by_line_253_AM.csv")