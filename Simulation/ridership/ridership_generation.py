"""

SOHEIL: gtfs2pt outputs with --use-gtfs-stopids will provide both lines and stopIDs.
# Stops needed for each trip is written in stop_times.txt in gtfs
# Todo: 1- using that option may result in creating duplicate stops with same IDs but on different edges/lanes.
# TODO: 2- double check line directions. I see inconsistencies in how gtfs2pt outputs use lineID or lineID#1
# currently the test files include bus routes "24", "33", "70", and "8"

--------------

gtfs2fcd.py gives each *distinct stop sequence* of a route its own line id, suffixing
duplicates with #1, #2 ... So one KCM route becomes several SUMO lines, and they are
mostly opposite directions:

    line 24    33 vehicles  Elliott Ave W & W Roy St   -> 3rd Ave & Cedar St
    line 24#1  35 vehicles  4th Ave S & S Royal Brougham -> Elliott Ave W & W Mercer Pl  (reverse)
    line 24#2   1 vehicle   Elliott Ave W & W Roy St   -> 3rd Ave S & S Main St
    line 8     70 vehicles  |  line 8#1   72 vehicles  (reverse)
    line 33    28 vehicles  |  line 33#1  31 vehicles  |  line 33#2   5
    line 70     8 vehicles  |  line 70#1  87 vehicles  |  line 70#2  85  |  line 70#3  9

The ridership CSVs only know `routeNum` ("24"), which normalises to the BASE line id, so
every personFlow is emitted with lines="24" / "8" / "33" / "70". Consequences:
  * the reverse-direction vehicles carry no passengers at all;
  * for route 70 the demand lands on the 8-vehicle variant while 181 other route-70
    vehicles run empty -- riders will queue at stops for a long time.

Three ways to resolve it (a modelling choice, deliberately NOT made here):
  b) emit a space-separated list, lines="24 24#1 24#2" (SUMO accepts a list) so a person may
     board any variant -- but a rider could then board a bus that never reaches their
     destination stop, so verify SUMO's boarding behaviour before relying on this;
  c) make generation direction-aware: use the ridership `direction` column (I/O), map each
     direction to the matching SUMO line variant by comparing terminal stops, and generate
     per-variant flows using that variant's own stop sequence. Most faithful, most work.
"""


import pandas as pd
import xml.etree.ElementTree as ET
from xml.dom import minidom
from collections import defaultdict



# Inputs
sumo_stop_file = "sumo_bus_stop_ids.csv"
ridership_file = r"kcm_ridership_matched_sumo_stops_253_AM.csv"
route_file = "../GTFS/bus/gtfs_pt_vehicles.add.xml"

output_person_file = "kcm_personflows_253_AM_with_alighting.rou.xml"

begin_time = 5 * 3600
end_time = 9 * 3600
duration_hours = 4


# Load SUMO bus stop IDs
sumo_stops = pd.read_csv(sumo_stop_file)

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
# for trip in root.findall("trip"):
for trip in root.findall("vehicle"):
    if trip.get("type") != "bus":
        continue

    line = trip.get("line")
    if line is None:
        continue
    # stops = [s.get("busStop") for s in trip.findall("stop") if s.get("busStop")]

    route_id = trip.get("route") # from gtfs2pt outputs, it is actually the trip id of the first trip that uses this route
    route= root.find(f'.//route[@id="{route_id}"]')
    stops = [s.get("busStop").split('_')[1] for s in route.findall("stop") if s.get("busStop")]
    if len(stops) >= 2:
        line_to_stop_sequences[line].append(stops)

print(line_to_stop_sequences.keys())
print(" figure out how #'s are coded")


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
            # persons_per_hour = assigned_boardings / duration_hours  # SOHEIL: I think numbers are already in hourly basis
            persons_per_hour = assigned_boardings
            persons_per_hour = persons_per_hour *10  #TODO SOHEIL: for test purposes -- REMOVE IT LATER

            #SOHEIL: codes below are duplicated with the loop below. can use a function to avoid duplication. but for now, just keep it as is.
            pf = ET.SubElement(routes_root, "personFlow", {
                "id": f"pf_{line}_{origin_stop}_{destination_stop}_AM_{created}",
                "begin": str(begin_time),
                "end": str(end_time),
                "personsPerHour": f"{persons_per_hour:.4f}"
            })

            # ET.SubElement(pf, "ride", {
            #     "from": origin_stop,
            #     "busStop": destination_stop,
            #     "lines": line
            # })
            # ET.SubElement(pf, "walk", {
            #     "from": sumo_stops[sumo_stops.stop_id==int(origin_stop)].lane.tolist()[0].split('_')[0],
            #     "busStop": 'gtfs_'+origin_stop,
            # })
            ET.SubElement(pf, "ride", {
                "from": sumo_stops[sumo_stops.stop_id == int(origin_stop)].lane.tolist()[0].split('_')[0],
                "to": sumo_stops[sumo_stops.stop_id == int(destination_stop)].lane.tolist()[0].split('_')[0],
                "busStop": 'gtfs_' + destination_stop,
                "lines": line
            })

            created += 1
            continue

        total_downstream_alight = downstream_df["tripAlightings"].sum()

        for _, dest_row in downstream_df.iterrows():
            destination_stop = dest_row["stopId"]
            alight_weight = dest_row["tripAlightings"] / total_downstream_alight

            assigned_boardings = boardings * alight_weight
            # persons_per_hour = assigned_boardings / duration_hours #SOHEIL: I think numbers are already in hourly basis
            persons_per_hour = assigned_boardings
            persons_per_hour = persons_per_hour *10  #TODO SOHEIL: for test purposes -- REMOVE IT LATER


            if persons_per_hour <= 0:
                continue

            pf = ET.SubElement(routes_root, "personFlow", {
                "id": f"pf_{line}_{origin_stop}_{destination_stop}_AM_{created}",
                "begin": str(begin_time),
                "end": str(end_time),
                "personsPerHour": f"{persons_per_hour:.4f}"
            })

            # ET.SubElement(pf, "ride", {
            #     "from": origin_stop,
            #     "busStop": destination_stop,
            #     "lines": line
            # })


            # ET.SubElement(pf, "walk", {
            #     "from": sumo_stops[sumo_stops.stop_id==int(origin_stop)].lane.tolist()[0].split('_')[0],
            #     "busStop": 'gtfs_'+origin_stop,
            # })
            ET.SubElement(pf, "ride", {
                "from": sumo_stops[sumo_stops.stop_id==int(origin_stop)].lane.tolist()[0].split('_')[0],
                "to": sumo_stops[sumo_stops.stop_id==int(destination_stop)].lane.tolist()[0].split('_')[0],
                "busStop": 'gtfs_'+destination_stop,
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
    "estimated_initial_load_by_line_253_AM.csv", index=False
)

print(f"Generated: {output_person_file}")
print(f"Person flows created: {created}")
print(f"Skipped rows: {len(skipped)}")
print("Saved estimated initial loads to: estimated_initial_load_by_line_253_AM.csv")