import xml.etree.ElementTree as ET
from xml.dom import minidom

input_file = "new_bus_link_route.rou.xml"
output_file = "new_bus_link_route_with_line.rou.xml"

tree = ET.parse(input_file)
root = tree.getroot()

for trip in root.findall("trip"):
    trip_id = trip.get("id")
    trip_type = trip.get("type")

    # Only process bus trips
    if trip_type != "bus":
        continue

    # Route name is before the first underscore
    # Examples:
    # 1_49195113 -> 1
    # E_Line_49194345 -> E_Line
    parts = trip_id.split("_")

    if len(parts) >= 3 and parts[1] == "Line":
        route_line = f"{parts[0]}_Line"
    else:
        route_line = parts[0]

    trip.set("line", route_line)

# Pretty print XML
xml_str = ET.tostring(root, encoding="utf-8")
pretty_xml = minidom.parseString(xml_str).toprettyxml(indent="    ")

with open(output_file, "w", encoding="utf-8") as f:
    f.write(pretty_xml)

print(f"Saved updated route file to: {output_file}")