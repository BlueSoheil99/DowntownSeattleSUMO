
import os
import pandas as pd


## SOHEIL: The stop IDs that are created from gtfs2pt in gtfs folder do not have the stop IDs from stops.txt of
# the gtfs files. so running this script does not work at its current format. One possible way is to fork gtfs2pt and
# make sure that generated stops have the correct stop_ids.
# Stops needed for each trip is written in stop_times.txt in gtfs



# Inputs
sumo_stop_file = "sumo_bus_stop_ids.csv"
ridership_root = "data/routeData/kcm"   # change if needed
# ridership_root = "data/routeData/st"   # change if needed
service_change = "253"
time_period = "AM"
prefix = "st"

# Load SUMO bus stop IDs
sumo_stops = pd.read_csv(sumo_stop_file)
sumo_stop_ids = set(sumo_stops["stop_id"].astype(str))

matched_rows = []
missing_routes = []

# Loop through all route folders
for route in os.listdir(ridership_root):

    route_folder = os.path.join(ridership_root, route, service_change)
    ridership_file = os.path.join(route_folder, "ridershipData.csv")

    # Check file existence
    if not os.path.exists(ridership_file):
        print(f"[Missing] {route}")
        missing_routes.append(route)
        continue

    # Load ridership file
    df = pd.read_csv(ridership_file)

    # Convert stopId to string for matching
    df["stopId"] = df["stopId"].astype(str)

    # Filter by SUMO stops and AM period
    df_match = df[
        (df["stopId"].isin(sumo_stop_ids)) &
        (df["timeOfDay"] == time_period)
    ].copy()

    if not df_match.empty:
        df_match["route_folder"] = route
        matched_rows.append(df_match)

# Combine matched rows
if matched_rows:
    matched_df = pd.concat(matched_rows, ignore_index=True)
else:
    matched_df = pd.DataFrame()

# Save matched data
output_file = f"{prefix}_ridership_matched_sumo_stops_{service_change}_{time_period}.csv"
matched_df.to_csv(output_file, index=False)

# Save missing routes
missing_df = pd.DataFrame({"missing_route_folder": missing_routes})
missing_df.to_csv(f"missing_ridership_routes_{prefix}.csv", index=False)

# Summary
print("\n========== SUMMARY ==========")
print(f"Matched rows: {len(matched_df)}")

if not matched_df.empty:
    print(f"Matched routes: {matched_df['routeNum'].nunique()}")
    print(f"Matched stops: {matched_df['stopId'].nunique()}")

print(f"Missing route folders: {len(missing_routes)}")

print(f"\nSaved matched data to:")
print(output_file)

print(f"\nSaved missing routes to:")
print(f"missing_ridership_routes_{prefix}.csv")