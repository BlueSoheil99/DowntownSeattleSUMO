import xml.etree.ElementTree as ET
from xml.dom import minidom

import pandas as pd
import zipfile

## SOHEIL: gtfs2pt outputs with --use-gtfs-stopids will provide both lines and stopIDs.
# so this code is basically redundant. If needed, just make sure when using the add file you also copy <route>s into the output
# TODO: double check line directions. I see inconsistencies in how gtfs2pt outputs use lineID or lineID#1

input_file = "../GTFS/bus/gtfs_pt_vehicles.add.xml"
gtfs_zip = "../GTFS/gtfs data/kcm_google_transit_downtown.zip"
output_file = "gtfs_pt_vehicles_with_line.rou.xml"


def open_gtfs(gtfs_path):
    gtfs = {}
    with zipfile.ZipFile(gtfs_path, 'r') as z:
        for file in z.namelist():
            if file.endswith(".txt"):
                gtfs[file] = pd.read_csv(z.open(file))
    return gtfs

def get_line_from_gtfs(trip_id, gtfs_path):
    gtfs = open_gtfs(gtfs_path)
    trips = gtfs['trips.txt']
    routes = gtfs['routes.txt']
    print(trip_id)
    trip_id = trip_id.split(".")[0] #if has '.trimmed' postfix
    route_id = trips.loc[trips.trip_id == int(trip_id), 'route_id'].iloc[0]
    route_name = routes.loc[routes.route_id == route_id, 'route_short_name'].iloc[0]
    return str(route_name)

tree = ET.parse(input_file)
root = tree.getroot()

# for trip in root.findall("trip"):
for trip in root.findall("route"):
    trip_id = trip.get("id")
    # trip_type = trip.get("type")
    trip_type = trip.get("type", 'bus')
    # default value is there since we know input is for buses but gtfs2pt did not explicitly write it

    # Only process bus trips
    if trip_type != "bus":
        continue

    # Route name is before the first underscore
    # Examples:
    # 1_49195113 -> 1
    # E_Line_49194345 -> E_Line
    # parts = trip_id.split("_")
    # if len(parts) >= 3 and parts[1] == "Line":
    #     route_line = f"{parts[0]}_Line"
    # else:
    #     route_line = parts[0]

    route_line = get_line_from_gtfs(trip_id, gtfs_zip)

    trip.set("line", route_line)

# Pretty print XML
xml_str = ET.tostring(root, encoding="utf-8")
pretty_xml = minidom.parseString(xml_str).toprettyxml(indent="    ")

with open(output_file, "w", encoding="utf-8") as f:
    f.write(pretty_xml)

print(f"Saved updated route file to: {output_file}")

