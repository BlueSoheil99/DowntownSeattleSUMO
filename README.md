# Simulation of Downtown Seattle AM peak
In this work, we simulated passenger vehicles and public transportation of Downtown seattle between 5 to 10 AM. The exact simulation period could be modified in step3 of demand generation and in sumocfg file. 
Our network includes south of Mercer St, west of 12th Ave, and north of S Holgate St.

<p align="center" width="100%">
    <img width="75%" src="https://github.com/BlueSoheil99/DowntownSeattleSUMO/blob/main/network%20image.png?raw=true"><br>
The network and the TAZs used in the simulation<br>
</p>

- For further questions, email [soheil99@uw.edu](mailto:soheil99@uw.edu)
- A more detailed documentation: [link](https://docs.google.com/document/d/1cB_eXvKE2OPgtG05p4Bbuse4nkuFutzw?rtpof=true&usp=drive_fs)
- This work was based upon the simulation in
https://github.com/Yiran6/MatSumo (private repo). It also included pedestrians. That simulation could be found in `simulation/old simulation files` folder.

Our work was divided into three sections, generating a  demand file (rou.xml) based on the real world, running a reasonable simulation in SUMO
, and calibration which is explained in the detailed document.

-------
## Demand generation
If you just want to run the simulation, skip this section.
Demand generation takes place in four steps and 
final output of each step is the input of the next step. Output of the 4th step is the input for the simulation (route file).
- **Step1: Trip generation**
  - Run `step1-read h5.ipynb`
  - Input(s): PSRC trip dataset, estimated for Puget sound population for one working day.
  <span style="color: red;"> Due to Github space limitation, the source file has not been uploaded yet.</span>
  Using a UW email, you can access through this [link](https://drive.google.com/drive/folders/1KIlRBGK1AhPe5t2rL66fhlWQGoFRLiWj?usp=sharing).

  - Output: `psrc_vehicle_trips.csv`, shows [otaz,dtaz,deptm,travtime] for each trip.
  - Description:
    - In this step, we work on trip data of individuals. Each row of the input file shows a trip for a person which could be done in different modes. 
    We first find trips done with cars. Then we try to remove the trips that were shared but used one vehicle (duplicate trips shared between different people).

  <p align="center" width="100%">
    <img width="60%" src="https://github.com/BlueSoheil99/DowntownSeattleSUMO/blob/main/departure%20distribution.png?raw=true"><br>
  Departure time of trips during 24 hours <br>
  </p>

- **Step2: TAZ calibration**
  - Run `step2-taz filteration_conversion-v.3.ipynb`
  - Input(s): `psrc_vehicle_trips.csv`, `taz2010.shp`, `correct_Alaskan_modified_new_Taz_with_pseudo.add.xml`, TAZ list of different super TAZs (`regions` folder)
  - Output:  `psrc_vehicle_trips_converted_taz_calibrated_v2.csv`, if either `otaz` or `dtaz` for an input row is not in the simulation network, it is changed to its corresponding pseudo TAZ.
  - Description:
    - For our network we do not have all Puget sound TAZs and just focus on Downtown Seattle.
    Therefore, when we want to simulate trips that go to(come from) out of Downtown Seattle, 
    we need to guess where they exit (enter) our network. 
    The TAZ.add.xml file we used has many pseudo TAZs (TAZs with #taz>=5000) to account for entering and exiting our network if desired in a trip.
    - This code replaces corresponding pseudo TAZs with TAZs that are not present in the simulation network (Downtown Seattle).
    - To develop this code, I assumed multiple super TAZs in King County (pictures are included in the code)
    and used Google Maps to guess how the route of trips from/to those super TAZs to/from Downtown will be and what pseudo TAZ they will pass through. Also, for the trips that have otaz out of downtown, I estimated the time distance from corresponding super TAZs to the assigend pseudo TAZs and adjusted those trips' `deptime` (which is the time they enter our network).
  
- **Step3: Route file (SUMO input) generation**
  - Run `step3-generate_rou.ipynb`
  - Input(s): `psrc_vehicle_trips_converted_taz_calibrated_v2.csv`,`correct_Alaskan_modified_new_Taz_with_pseudo.add.xml`, start and end time of demand insertion, 
  
  - Output: `alaskanway_od2trips_psrc_vehicle_trips_converted_taz_calibrated_V2.rou.xml`, copy and paste it in the `Simulation` folder.
  - Description:
    - In the final step for demand generation, we can generate route files in two ways:
    1) Using [od2trips](https://sumo.dlr.de/docs/od2trips.html).
    Based on definition of TAZs, it gives us a source and a sink link for each trip.
    If TAZs are not defined properly or there is no connection in simulation network between origin and destination links,
    the simulation will not insert that trip or will crash.
    In this method, we make an OD table for trips of each 15-minute interval and then call `od2trips` for each OD table.
    You should manually add vType (like the example below) before definition of trips
         
       `  <vType id="passenger" vClass="passenger" accel="3.2" color="yellow" decel="3.5" length="4" maxSpeed="200" lcStrategic="1" lcSpeedGain="1" lcCooperative="1" lcSpeedGainLookahead="5" minGap="1.5" cc1="0.9" cc2="4" cc3="-8" cc4="-0.1" cc5="0.1" cc6="11.44" cc7="0.25" cc8="3.5" cc9="1.5"/>`
    -- You can change car following and lane changing parameters
       - Remember: if you use the first method (od2trips), make sure that you are using the exact TAZ file used in the simulation (in case you change something in this file in `simulation` folder and want to generate demand in `Demand generation` folder) 
       - TAZs have multiple source and sink links, and they are assigned to the generated trips based on their probability of being used, which is their normalized weight in that TAZ.
       Using `misc.ipynb`, we set the weight of sink and source links of each TAZ same as their priority in the network.
    2) Manually writing trips based on their origin and destination TAZ. In this method, simulation will be faster and SUMO will choose origin and destination links
    in a way that the trip has the shortest route. As a result, trips will start and end on outer links of a TAZ. 
    - We prefer the first method since all links will be used in each TAZ,
    and it looks more realistic. In second method, you would see some links in a TAZ are destination of many trips, 
    while their neighbor links in the same TAZs do not get utilized.
   

    
- **Step4: Make little adjustments**
  - Run `misc.ipynb` in `simulation` folder.
  - Input(s): `(TAZ or od2trips)_psrc_vehicle_trips_converted_taz.rou.xml`
  - Output: adjusted and/or reduced version of input
  - Description: We may want to make an adjustment or a reduction to the result of 3rd step:
    - Use it after generating the demand file and copying it into `simulation` folder.
    - We perform reduction for some TAZs (like SR99-north south bound), since they become very congested and get clear
    after a relatively long time after 10 AM. What we want is that vehicle insertion onto the network stops after 20-30 minutes maximum.
    In the related code in `misc.ipynb`, we can also transfer a specific percentage of demand from one origin TAZ
    to another Origin TAZ. In fact, we transferred some of the inflow from SR99-north to I5-north.
    - In the 3rd step, we were able to generate the demand in two formats: 1) TAZ to/from TAZ and 2) link to/from link.
    However, there is another format that was not mentioned in SUMO documentations, **TAZ to/from link** format.
    For example, for a trip in the `od2trip` result, we can remove the attribute `from` and keep the `fromTAZ` attribute.
    In this case, SUMO will insert the vehicle in a link in the origin TAZ that is the closest link to the destination link assigned in `od2trips` command.
    - For two reason, we change the result of `od2trip` command from link-link to TAZ-link for some TAZs:
      1) When people are coming into the network through pseudo TAZs, we can assume that the link by which they enter the network is the closest link to their destination in that pseudo TAZ.
      So for using pseudo TAZs, we do not have to randomly set a specific link to be used by each trip.
      2) One way to get into the TAZs in north-west of our network (west of I5 and north of Denny way)
      is by passing Mercer St. Since we don't have Mercer St. in our network, we had to add on/off ramps for Mercer St. to those TAZs. 
      We assume that if someone wants to go to (come from) those TAZs using Mercer St.,
      they will enter (exit) those ramps. This could be the case for trips that have destination or origin far from those TAZs.
      Trips from closer proximity, like trips that have one end in Denny triangle, won't use those ramps. 
      So, in the demand file, trips with one end in north-west TAZs should be in TAZ-link format and we don't use specific links in those TAZs.
    


----
## Simulation
To run the simulation, you have to:
1) Have SUMO installed on your system.
2) Install python packages in `requirements.txt`
3) Make sure that `sumocfg` file contains the right network, TAZ, and demand file.
4) Run `run_simulation.py` file
5) Find the output results in `new output` folder.


- Some of the signals in `offset_signal_Seattle_network_reformed connections2.net.xml` were manually changed. 
To use the original specification of traffic signals, use 
`no_alley_Seattle_network_reformed connections.net.xml` instead. Note that this network probably won't work well with 
route files generated with od2trips.
- If you decide to change the hours to something else rather than 5-10am, remove additional demand of public transit in `bus_link_route.rou.xml` and replace it with 
    `new_bus_link_route.rou.xml` in `clean corrected inputs` folder.

----
## Results
Outputs for the final calibrated simulation are in `Simulation/May6 final` folder. The folder includes:
* edge data for each hour which will be used for segmentation of dowtown Seattle network ([link](https://sumo.dlr.de/docs/Simulation/Output/Lane-_or_Edge-based_Traffic_Measures.html))
* Log file
* Data for loop detectors used for corridor calibration
* trip info ( [link](https://sumo.dlr.de/docs/Simulation/Output/TripInfo.html))
* signal-report file which shows average cycle time between 8-9AM and average green time for each approaching lane

And three files that were not uploaded for their big size:
* Edge data for each minute which can be used for MFD generation
* Vehicle routes ([link](https://sumo.dlr.de/docs/Simulation/Output/VehRoutes.html))
* vehRouteTime fine where for each trip,
it shows departure time and the time taken on each edge of the route