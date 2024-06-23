import sys
import traci
# import xml.etree.ElementTree as ET
from SignalTracker import SignalTracker
import pandas as pd
import pickle


def update_vehicle(vehicleID, current_step, vehicles_tt_dict, finished=False):
    vehicle_data = vehicles_tt_dict.get(vehicleID)
    try:
        if finished:
            last_edge = vehicle_data['last_edge']
            last_time = vehicle_data['last_edge_start_step']
            duration = (current_step - last_time)
            # duration = (current_step - last_time)/10
            vehicle_data['route times'][last_edge] = duration
            vehicle_data['arrival']= current_step
            vehicle_data['travel_time'] = (current_step - vehicle_data['departure'])/10
            vehicle_data['captured_travel_time'] = sum(vehicle_data['route times'].values())/10
        else:
            edge = traci.vehicle.getRoadID(vehicleID)
            if edge == "":
                edge = f"EmptyString@{current_step}"
            if vehicle_data is None:
                d = {'last_edge': edge, 'last_edge_start_step': current_step, 'route times': dict(),
                     'departure':current_step, 'arrival': 0, 'travel_time': 0, 'captured_travel_time': 0}
                vehicles_tt_dict[vehicleID] = d
            else:
                last_edge = vehicle_data['last_edge']
                # if (last_edge != edge):
                if (edge[0] != ':') and (last_edge != edge):
                    last_time = vehicle_data['last_edge_start_step']
                    duration = current_step - last_time
                    vehicle_data['last_edge_start_step'] = current_step
                    vehicle_data['last_edge'] = edge
                    vehicle_data['route times'][last_edge] = duration
    except Exception as e:
        print(e)
        print(f'step: {current_step} -- vehicle id: {vehicleID}')
        # update_vehicle(vehicleID, current_step, vehicles_tt_dict, finished=True)



#######################################
### 1- CONNECT TO SUMO SIMULATION TOOL
#######################################
# traci.start(["sumo-gui", "-c", "Bigger_Seattle.sumocfg"])
##  The simulation above is the old one used in https://github.com/Yiran6/MatSumo. We used this as the basis of our work
# traci.start(["sumo-gui", "-c", "test_fariviewAve_reformed_Seattle.sumocfg"])
## In the simulation above, we tried to force vehicles used fairview avenue (which is a main street) using corridor
## coordination, increasing speed, increasing priority, etc. The problem was that without the second part of this code,
## vehicles did not have reasonable routing and were using roads with low priority too much.
traci.start(["sumo-gui", "-c", "clean_reformed_Seattle.sumocfg"])

################################################
### 2- ELIMINATE THE EFFECT OF PEDESTRAIN LANES
## we used the commented lines in part 3 and found out that the speed of pedestrian lanes in the latest version of SUMO
## negatively affects the travel time of edges. This resulted in writing this part.
## https://github.com/eclipse-sumo/sumo/issues/14181
################################################
SMALL_SPEED_LIMIT = 8.94  # meter per second --  20 mph
# we use this speed if we can't find the speed limit of adjacent vehicle lane
lane_ids = traci.lane.getIDList()
for lane_id in lane_ids:
    if "pedestrian" in traci.lane.getAllowed(lane_id):
        # set pedestrian disallowed and adjust the speed limit to vehicles'
        # traci.lane.setDisallowed(lane_id, "pedestrian")
        ref_lane = lane_id[:-2] + "_1"
        if ref_lane in lane_ids:
            speed_limit = traci.lane.getMaxSpeed(ref_lane)
        else:
            speed_limit = SMALL_SPEED_LIMIT
        # if speed_limit < SMALL_SPEED_LIMIT:
        #     print(lane_id, speed_limit)
        traci.lane.setMaxSpeed(lane_id, speed_limit)


################################################
### 3- REDUCING SPEED LIMITS FOR 5MPH
################################################
'''
# change 50 and 100 kph to 13.41 mps or 30mph
prohib_speeds=[13.89, 27.78]
for lane_id in lane_ids:
    priority=traci.lane.getPriority(lane_id)
    if priority <10:
        ref_speed = traci.lane.getMaxSpeed(lane_id)
        if ref_speed in prohib_speeds:
            traci.lane.setMaxSpeed(lane_id, 13.41)
# change (in order) 11.18 to 8.84, 13.41 to 11.18, and 15.65 to 13.41
change_map = {11.18:8.84, 13.41:11.18, 15.65:13.41}
for speed in change_map.keys():
    for lane_id in lane_ids:
        priority=traci.lane.getPriority(lane_id)
        if priority <10:
            ref_speed = traci.lane.getMaxSpeed(lane_id)
            if ref_speed==speed:
                traci.lane.setMaxSpeed(lane_id, change_map[speed])
'''
# read lane IDs and exclude the ones with high priority (highway links). They have the right speed
f = open('links_w_priority_over10.txt', 'r')
high_p_edges = f.readlines()
high_p_edges = [line[5:-1] for line in high_p_edges]
lane_ids = traci.lane.getIDList()
lane_ids = [line for line in lane_ids if line[:-2] not in high_p_edges]

# change 50 and 100 kph to 13.41 mps or 30mph
prohib_speeds=[13.89, 27.78]
for lane_id in lane_ids:
    ref_speed = traci.lane.getMaxSpeed(lane_id)
    if ref_speed in prohib_speeds:
        traci.lane.setMaxSpeed(lane_id, 13.41)
# change (in order) 11.18 to 8.84, 13.41 to 11.18, and 15.65 to 13.41
change_map = {11.18:8.84, 13.41:11.18, 15.65:13.41}
change_order = [11.18, 13.41, 15.65]
for speed in change_order:
    for lane_id in lane_ids:
        ref_speed = traci.lane.getMaxSpeed(lane_id)
        if ref_speed==speed:
            traci.lane.setMaxSpeed(lane_id, change_map[speed])
# save network--- cant do it :(


###############################
### 4- setup signal info tracker values
###############################
# simulation_hour_begin = 5.0
# segmentation_hour_begin = 5.05
# segmentation_hour_end = 5.1
# segmentation_step_begin = int((segmentation_hour_begin - simulation_hour_begin)*3600*10)
# segmentation_step_end = int((segmentation_hour_end - simulation_hour_begin)*3600*10)

# simulation_hour_begin = 5.0
# segmentation_hour_begin = 5.05
# segmentation_hour_end = 5.1

segmentation_step_begin = 3*3600*10
segmentation_step_end = 4*3600*10
signals = []
tl = traci.trafficlight


###############################
### 5- RUN THE SIMULATION LOOP
###############################
trip_info_address = 'new output/vehRouteTime_output.pickle'
trip_travel_time_data = dict()
vehicleIDs = set()

last_step = 20*60
step = 0
# while step < last_step:  # uncomment this if you want the simulation stop in a certain time
while traci.simulation.getMinExpectedNumber() > 0:
    traci.simulationStep()
    step += 1

    if step%10 == 0: # we check this every second
        if step == segmentation_step_begin:
            for tlsID in tl.getIDList():
                signals.append(SignalTracker(tlsID, tl, step//10))
        if step > segmentation_step_begin and step < segmentation_step_end:
            for signal in signals:
                signal.update(tl)
        if step == segmentation_step_end:
            data = {'id':[], 'hasProblem':[], 'avgCycle':[], 'lanes':[], 'avgTimes':[]}
            for signal in signals:
                signal.stop(step//10)
                data['id'].append(signal.ID)
                data['hasProblem'].append(signal.hasProblem)
                data['avgCycle'].append(signal.avgCycleTime)
                data['lanes'].append(list(signal.laneTimeDict.keys()))
                data['avgTimes'].append(list(signal.laneTimeDict.values()))

            # signals_to_csv(signals)
            data = pd.DataFrame(data=data)
            data.to_csv(f'new output/signal_report{segmentation_step_begin}_{segmentation_step_end}.csv',
                        index=False)

    ## updating travel times of vehicles ##
    departed_vhs = traci.simulation.getDepartedIDList()
    arrived_vhs = set(traci.simulation.getArrivedIDList())
    vehicleIDs = vehicleIDs.union(departed_vhs)
    # finish timing for arrived vehicles
    for vehicleID in arrived_vhs:
        if '_' not in vehicleID:
            update_vehicle(vehicleID, step, trip_travel_time_data, finished=True)
    vehicleIDs -= arrived_vhs
    # updating vehicles not arriving yet
    if step%5==0:  # update every half second
        for vehicleID in vehicleIDs:
            if '_' not in vehicleID:   # exclude transit IDs
                update_vehicle(vehicleID, step, trip_travel_time_data, finished=False)

    print(f'step: {step}')


# trip_travel_time_data = {edge:trip_travel_time_data[edge]['route times'] for edge in trip_travel_time_data.keys()}
with open(trip_info_address, 'wb') as f:
    pickle.dump(trip_travel_time_data, f)

# Close TraCI connection
traci.close()
sys.stdout.flush()

# # observe the travel time on links
# observed_id = "-428087138#0"
# left_id = "-6464775#4"
# right_id = "-560096281#2"
# travel_time = traci.edge.getTraveltime(observed_id)
# print("center street: {}. Speed limit: {}".format(travel_time, traci.lane.getMaxSpeed("{}_1".format(observed_id))))
# print("left street: {}. Speed limit: {}".format(traci.edge.getTraveltime(left_id), traci.lane.getMaxSpeed("{}_1".format(left_id))))
# print("right street: {}. Speed limit: {}".format(traci.edge.getTraveltime(right_id), traci.lane.getMaxSpeed("{}_1".format(right_id))))
