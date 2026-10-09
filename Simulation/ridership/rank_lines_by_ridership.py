# Ranks the downtown bus lines in GTFS/bus/DT_seattle_Buslines.txt by ridership inside the bus filter bbox
# (sum of dailyBoardings in the latest period of ridership/data/routeData/kcm/<route>/<period>/ridershipData.csv).
# Run from Simulation/: python ridership/rank_lines_by_ridership.py  ->  GTFS/bus/DT_buslines_ridership_ranking.csv
import zipfile, io, pandas as pd, os
base = "ridership/data/routeData/kcm"
with zipfile.ZipFile("GTFS/gtfs data/kcm_google_transit.zip") as z:
    stops = pd.read_csv(z.open("stops.txt"), usecols=["stop_id","stop_lat","stop_lon"])
stops["stop_id"] = stops["stop_id"].astype(str)
inbox = set(stops[(stops.stop_lat.between(47.58,47.65)) & (stops.stop_lon.between(-122.37,-122.30))].stop_id)
groups = {"DT":"1,2,3,4,5,7,8,10,11,12,13,14,17,21,24,27,28,33,36,40,49,56,57,62,70,101,102,105,113,121,124,125,131,132,150,256,322",
          "CapHill":"9,43,60", "Edge":"31,32,106"}
rows=[]
for g,ls in groups.items():
    for r in ls.split(","):
        d=f"{base}/{r}"
        if not os.path.isdir(d): rows.append((g,r,None,None,None,None)); continue
        per=max(os.listdir(d), key=int)
        df=pd.read_csv(f"{d}/{per}/ridershipData.csv"); df["stopId"]=df.stopId.astype(str)
        ins=df[df.stopId.isin(inbox)]
        am=ins[ins.timeOfDay=="AM"]
        rows.append((g,r,per,round(df.dailyBoardings.sum()),round(ins.dailyBoardings.sum()),round(am.dailyBoardings.sum())))
t=pd.DataFrame(rows,columns=["group","route","period","route_daily","area_daily","area_AM"]).sort_values("area_daily",ascending=False)
t.insert(0,"rank",range(1,len(t)+1))
t.to_csv("GTFS/bus/DT_buslines_ridership_ranking.csv",index=False)
print(t.to_string(index=False))
