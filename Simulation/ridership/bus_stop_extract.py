import xml.etree.ElementTree as ET
import pandas as pd

# Input SUMO additional file
xml_path = "../GTFS/bus/gtfs_pt_stops.add.xml"

# Parse XML
tree = ET.parse(xml_path)
root = tree.getroot()

# Extract bus stop information
bus_stops = []

for bus_stop in root.findall("busStop"):
    bus_stops.append({
        "stop_id": bus_stop.get("id").split('_')[1],
        "lane": bus_stop.get("lane"),
        "startPos": bus_stop.get("startPos"),
        "endPos": bus_stop.get("endPos")
    })

# Convert to dataframe
bus_stop_df = pd.DataFrame(bus_stops)

# Save output
bus_stop_df.to_csv("sumo_bus_stop_ids.csv", index=False)

print(f"Number of bus stops extracted: {len(bus_stop_df)}")
print(bus_stop_df.head())