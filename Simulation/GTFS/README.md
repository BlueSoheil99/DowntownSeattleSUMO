# read this before working on gtfs/DT simulation

### 1-this work was start by Zili Qu. 
She has a doc about the things she did. Read her stuff in `/Zili` first. 

### 2- in this directory, I regenerated her work. 
you can run `simulation.sumocfg` to run the modified verion or Zili's train or bus simulations. 
Here I fixed some network issues first (some rail tracks were not connected properly in `Zili\rail\toy network\seattle_lightrail_full.net.xml'` and in `merged.net.xml` that Zili made)
, then ran her codes to regenerate sumo files for bus and rail gtfs separately, and then combined them to make a simulation with both bus and rail.

### 3- debugging is needed
- Format:
    - `gtfs2pt` outputs are `add.xml` files and demand is not in `rou.xml` files. maybe it's better to have `rou.xml` file for demand. 
    - make sure that stop and trip names are what we expect based on GTFS files. This is particularly important regarding working with codes in `ridership`.
- Rail: 
    - we can do some preprocessing on gtfs data so that we only capture trips between Judkins park, UW, and SODO. the filtering that the code currently does is not effective. This one is also not very important but it would be nicer not to have a very big area for simulation. 

network: 
- run the `netconvert` command in the notebook one more time. you will recieve some network warnings. I suggest spending some time to find geometry issues of the network. By correct premissions in `soheil_seattle_correct_premissions` we mean that we allowed 'tram' for rail tracks and that was needed to make gtfs2pt work with no errors. 
- (**You may ignore the following network issues. soheil_seattle_merged.net.xml works well with older sim files. didn't remove them to keep track later.**)
  - The way Zili used SUMO commands to merge rail network (only the parts that were out of DT)
  and the older network file (the one in `/clean corrected inputs`) leads to some artifacts. For example, compare the old `.net.xml` file with the new one in this folder and see what happened to SR99 entrance.
  I think the best way to complement the rail network is simply by adding new edges from the rail network to the xml file of the old network directly,
  without using netedit or netconvert. 
  - I tried adding manually. not a good idea. coordinates mess up and gtfs2pt won't work properly. the reason behind Zili's 
  network problem is that her rail network has nodes like J0 and edges like E1. there are similar nodes/edges in the DT network. so I chnaged those names in the rail network and tried Zili's work again

<p align="center">
  <img src="img.png" width="40%">
</p>

![img_1.png](img_1.png)

![img_2.png](img_2.png)

Bus:
- This is the main part that needs to be addressed. see below
- first of all: bus routes seems to be bad. they don't take most obvious routes! see screenshot below for a bus in line 8. 
could be a premission issue or speed issue. Probably the later because from old sim we know old network has some speed issues when sidewalks have low speeds compared to vehicle lanes.
![img_3.png](img_3.png)

- second: buses need to filtered and then added to the network. current filterning method is not very good (in notebook file)
Below is ChatGPT review of what we need to address for bus trips. I asked it to read ipynb file and the log when gtfs2pt is run for bus gtfs.

- In general, the proper workflow should include selecting specific routes, filtering them properly to be suitable for the incomplete network we have, and then run gtfs2pt on that. after that, we should carefully read the `gtfs2pt` log  and look at the simulation and how buses behave in simulation compared to our expectation. 

- Note that if you run Zili's bus simulation, you would face an error in simulation. that simulation is based on 12 routes that can be found in the ipynb file. Obviously this error should be fixed.

---------------------

# Review of `gtfs2pt.py` Log for KCM Bus Lines

The `gtfs2pt.py` command for the KCM bus GTFS appears to **run successfully**, but the output should **not be considered fully reliable yet**.

The script does not crash, and it does generate output files. However, the log shows several warning signs that the bus routes are not being mapped cleanly to the SUMO network.

## What Looks OK

The command successfully loads the SUMO network and the filtered GTFS file:

```text
Loading net
Loading GTFS data "gtfs data/kcm_google_transit_downtown.zip"
Success.
Writing fcd file "fcd\gtfs\bus.fcd.xml"
mapping bus
```

This means the basic inputs are readable:

- the SUMO network file is accepted;
- the filtered KCM GTFS zip is accepted;
- the selected bus GTFS data can be processed;
- the script is able to start generating bus-related SUMO output.

So, from a purely technical standpoint, the import process runs.

## Main Problems in the Log

### 1. Some GTFS points have no candidate SUMO edges

The log reports messages like:

```text
Found no candidate edges for ...
7 Points had no candidates.
```

This means some GTFS stop or trace points could not be matched to nearby usable SUMO road edges.

This is usually caused by one or more of the following:

- the stop is outside the SUMO network boundary;
- the stop is near the network edge but not close enough to a valid edge;
- the road exists geographically but is missing from the SUMO network;
- the edge exists but does not allow buses;
- the search radius is too small;
- the GTFS stop coordinate is closer to the wrong side of a divided road or one-way street.

This is a warning sign because if stops cannot be matched correctly, the generated public transport routes may become incomplete or distorted.

### 2. Some mapped routes have very large detour factors

The log reports large detour factors, for example:

```text
detour (factor 26.79)
detour (factor 17.55)
detour (factor 13.63)
```

These are not normal for a clean import.

A large detour factor means SUMO found a path between two mapped points, but that path is much longer than expected. For example, a detour factor of `26.79` means the mapped route segment is almost 27 times longer than the direct distance between the two points.

This usually means one or more of the following:

- stops are mapped to the wrong edges;
- stops are mapped to the wrong travel direction;
- the network is disconnected;
- bus access is not allowed on the expected road edges;
- the route is forced to take an unrealistic path;
- the filtered GTFS trip was chopped and no longer represents a realistic continuous route.

This is a serious quality issue. Even if SUMO generates a route, the route may not represent the actual bus movement.

### 3. Some bus routes are disconnected

The most serious warning is of this form:

```text
Warning! Disconnected route '800890320' between '456124866' and '460421475#1', no path found. Keeping longer part.
```

This means SUMO could not find a valid path between two consecutive mapped route segments.

When this happens, `gtfs2pt.py` keeps only the longer connected part of the route and discards the disconnected part.

That means some bus routes are likely being **silently shortened or chopped**.

This is especially important because the script may still finish successfully, but the generated bus routes may no longer match the intended GTFS service.

## Overall Diagnosis

The bus GTFS import is **technically successful but not clean**.

The output is useful for inspection and debugging, but I would not yet trust it for final simulation runs.

The main issues are:

- some GTFS points cannot be mapped to SUMO edges;
- some mapped route segments have unrealistic detours;
- some routes are disconnected;
- some generated bus routes may be incomplete;
- the filtered downtown-only GTFS may have created chopped trips.

The rail/tram import looked much cleaner. The KCM bus import has real mapping and network-connectivity issues that should be fixed before using the generated bus demand seriously.

## Suggestions: What to Do and What to Fix

- **Avoid clipping GTFS only by stops inside the bounding box without checking trip continuity.** This can create partial trips and disconnected route fragments.
- **Inspect the problematic stop IDs and edge IDs from the log** in NetEdit or with a simple map plot.
- **Verify bus permissions on the relevant SUMO edges.** Missing bus access can cause no-path and detour problems.
- **Check network connectivity near the problematic edges.** Some roads may be disconnected, one-way in the wrong direction, or missing turn connections.
- **Only adjust stop-matching radius after checking geometry.** A larger radius can help, but it can also map stops to wrong edges.
- **Consider importing fuller KCM trips first, then limiting demand or simulation area later**, instead of aggressively clipping the GTFS before running `gtfs2pt.py`.

---------------------

# Updates (October 2026)

## SUMO version: nightly build
`seattle_sumo_gtfsData_setup.ipynb` now runs gtfs2pt from a SUMO **nightly build**, `v1_27_1+0902-aab68b732de` (downloaded 2026-10-05), because it has gtfs2pt fixes that are not in the 1.27.1 release:
- #18237: duplicate busStop ids with `--use-gtfs-stopids`. The release writes e.g. `gtfs_1610` twice and sumo fails with "probably declared twice"; the nightly names the extra copy `gtfs_1610#1`. Because of this the old `dedupe_pt_stops` clean-up step was removed from the notebook, so **the notebook needs the nightly (or the next release)**.
- #18291: stale `resources/` cache reused after the network changes.
- #18238: trips with the same stops but different timing get their own route, so a line now has one route per timetable variant (e.g. 17 D Line routes for 5 stop patterns). Each vehicle's `line` is then `D_Line`, `D_Line#1`, ... instead of `D Line`. The ridership person flows (`lines="..."`) still use the plain name, so passengers only board the first variant. **Open issue** for the ridership simulation.

Setup (Windows):
- Download https://sumo.dlr.de/daily/sumo-win64-git.zip (the "Windows 64-bit zip" on https://sumo.dlr.de/docs/Downloads.php#nightly_snapshots), unzip it (e.g. to `C:\Users\<you>\sumo-nightly\sumo-win64-git`) and point `NIGHTLY_HOME` in the notebook's "FOR WINDOWS" cell at it. `USE_NIGHTLY = True` uses it; if the folder isn't found the cell says so and falls back to the installed release. The installed release is left as it is.
- The SUMO installer sets a machine-wide `PYTHONPATH` to the release's `tools` folder, which wins over `SUMO_HOME`. The setup cell overrides `PYTHONPATH` and `PATH` for the kernel and for the `!python` gtfs2pt calls, so restart the kernel and run the setup cell first.
- The nightly names its `resources/gtfs/` cache files after the network file's path. Pass the network as a short relative name (as the notebook does), otherwise Windows' 260-character path limit can be hit.
- To open files in the nightly GUI, run `sumo-gui.exe` from the nightly's `bin` folder (start-menu shortcuts still open the release).

## Bus stop snapping (`snap_gtfs_stops_to_network`)
gtfs2pt puts each stop on whichever route edge is closest to the GTFS coordinate. That goes wrong at junctions (the cross street is closer, so the bus loops around to reach it), at the network boundary (a stop beyond the network snaps onto a `pseudo*` edge) and on opposite sides of the same street. The notebook cell right after the bus filtering cell fixes the filtered zip **before** gtfs2pt runs. For every stop:
1. The direction of travel comes from `shapes.txt`, at the stop's `shape_dist_traveled` (falls back to the nearest shape segment if that is missing). This matters for loops: the G Line passes Madison St & Terry Ave in both directions about 10 m apart.
2. Candidate edges allow buses, are within 35 m and head within 45 deg of the travel direction. `pseudo*` boundary edges and motorway mainlines don't count.
3. Candidate found: the stop coordinate is moved onto the nearest one, kept 7 m from the edge ends so it can't snap onto the neighbouring edge at the junction.
4. No real bus edge at all within 35 m: the stop is outside the network and is removed from the timetable, so the trip ends at the previous stop (trips left with fewer than 2 stops are removed).
5. Real edges nearby but none in the travel direction: the stop is left unchanged and printed as a WARNING. This usually means a network direction or permission problem worth fixing rather than hiding.
6. Stops pinned in `bus/patched_stops.add.xml` are left to the pin (commented-out pins don't count). The file currently has no active pins (stop 1559 is handled by snapping) but must stay, since gtfs2pt is called with `--patched-stops`.

The cell rewrites `gtfs data/kcm_google_transit_downtown.zip` in place, so always run the filtering cell before it. Run order: setup cell, bus filtering, snapping, bus gtfs2pt. Delete `resources/` and `fcd/` after any network change.

## Network patches (`additional_net/`)
The source map predates some street changes and stops at W Republican St, so several bus lines were routed around missing streets. All hand-made network patches are kept in `additional_net/` and have been applied to `soheil_seattle_merged.net.xml`; `soheil_seattle_merged_pedspeed.net.xml` was then regenerated with the ped-speed cell in `seattle_sumo_network_setup.ipynb` (which also writes `additional_net/ped_speed_patch.edg.xml`).

| Patch | Files | What it adds |
|---|---|---|
| Columbia St eastbound bus lane | `columbia_eb_bus.edg.xml`, `.con.xml`, `.tll.xml` | Bus-only eastbound lane on Columbia St from Alaskan Way to 3rd Ave (edges `-635483971` ... `-370819917#1`; the 2019 change is missing from the map), with the south sidewalk moved from the westbound edges onto it. Fixes the northbound C Line looping around the block. The signal programs at Alaskan Way, 1st, 2nd and 3rd Ave are the originals plus one link per new bus movement. |
| Mercer St, Elliott Ave W to Warren Ave N | `mercer_st.nod.xml`, `.edg.xml`, `.con.xml`, `mercer_st_pass2.con.xml` | From current OSM geometry: W Mercer Pl, with the ramp off southeast-bound Elliott and the link back onto northwest-bound Elliott (priority junction, Elliott keeps priority), and W Mercer St / Mercer St (1 lane each way west of 2nd Ave W, 2 each way east of it, sidewalks, 25 mph). Connects 4th/3rd/2nd/1st Ave W, Queen Anne Ave N (southbound) and 1st Ave N (northbound, extended 30 m). Default signals at 3rd Ave W, 2nd Ave W, 1st Ave W, Queen Anne Ave N, 1st Ave N and Warren Ave N. Fixes the D Line's misplaced stops and U-turn. Elliott, 1st Ave W and Warren Ave N are split where they meet it; the Elliott pieces at the network boundary keep their original ids (`22759220#9`, `-22759220#9`) because they are TAZ sources/sinks. |
| Small connection repairs | `network_fixes.con.xml` | 3rd Ave northbound from Wall St to Vine St (`370785080#0`) had no outgoing connections at Vine St, so the northbound D Line detoured via Wall St and Vine St. |

Related: `clean corrected inputs/correct_Alaskan_new_signal_additional_columbia_eb.add.xml` is a copy of the signal additional with the Columbia St programs extended to match. `gtfs_ridership_vehicular.sumocfg` and `gtfs_transit_only.sumocfg` use it; the original is still used by the configs on the older network.

**If `soheil_seattle_merged.net.xml` is ever regenerated, reapply the patches in this order** (run from this folder), then rerun the ped-speed cell. Mercer St needs two passes: the second removes a connection that only exists after Elliott is split. Existing edges keep their stored connections when edges are added next to them, so turns from former dead ends are listed explicitly in the `.con.xml` files.
```
netconvert -s soheil_seattle_merged.net.xml -e additional_net/columbia_eb_bus.edg.xml -x additional_net/columbia_eb_bus.con.xml -i additional_net/columbia_eb_bus.tll.xml --no-turnarounds -o soheil_seattle_merged.net.xml
netconvert -s soheil_seattle_merged.net.xml -n additional_net/mercer_st.nod.xml -e additional_net/mercer_st.edg.xml -x additional_net/mercer_st.con.xml --no-turnarounds -o soheil_seattle_merged.net.xml
netconvert -s soheil_seattle_merged.net.xml -x additional_net/mercer_st_pass2.con.xml --no-turnarounds -o soheil_seattle_merged.net.xml
netconvert -s soheil_seattle_merged.net.xml -x additional_net/network_fixes.con.xml --no-turnarounds -o soheil_seattle_merged.net.xml
```
