

class SignalTracker:
    def __init__(self, ID, tl, start_time):
        self.start = start_time
        self.ID = ID
        self.cycleCount = 1
        self.currentPhase = tl.getPhase(self.ID)
        self.originalPhase = tl.getPhase(self.ID)
        self.lanes = tl.getControlledLanes(self.ID)
        self.laneTimeDict = {lane:0 for lane in set(self.lanes)}
        self.hasProblem = False
        self._update_times(tl)

    def stop(self, end_time):
        # self.cycleCount -= 1
        self.avgCycleTime = (end_time - self.start)//self.cycleCount
        self.laneTimeDict = {lane: totaltime//self.cycleCount for lane, totaltime in self.laneTimeDict.items()}

    def __str__(self):
        return f'ID: {self.ID}, cycles: {self.cycleCount}, times: {self.laneTimeDict}'

    def update(self, tl):
        if not self.hasProblem:
            phase = tl.getPhase(self.ID)
            # if self.ID == '53155395':   # debug
            #     print(f'phase for {self.ID}:  {phase}')
            if phase != self.currentPhase:  # have we entered this phase info before?
                if phase == self.originalPhase:  # have we just completed a cycle for this light?
                    self.cycleCount += 1
                self.currentPhase = phase
                self._update_times(tl)

    def _update_times(self, tl):
        phaseLength = tl.getPhaseDuration(self.ID)
        state = tl.getRedYellowGreenState(self.ID).upper()
        lanesStatus = {lane:False for lane in set(self.lanes)}
        try:
            for i in range(len(state)):
                if state[i] == 'G':  # if one state is green
                    # todo the problem: sometimes state doesn't not match lanes
                    if lanesStatus[self.lanes[i]] is False:  # if we have not added phase length for this lane before
                        # print(self.lanes[i])
                        self.laneTimeDict[self.lanes[i]] += phaseLength
                        lanesStatus[self.lanes[i]] = True
        except:
            self.hasProblem = True
            print(f'oops {self.ID}')

