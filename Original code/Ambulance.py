########################################
# Simulation for SALT -- Ambulance
# last update 09/06/18
########################################

import sys

class Ambulance():

    # constructor
    def __init__(self, vehicle_type, station):
        self.vehicle_type = vehicle_type
        self.station = station
        self.isBusy = False
        self.timeToClear = 10000.0
        self.totalBusyTime = 0.0

    def setBusy(self, time):
        if self.isBusy == False:
            self.isBusy = True
            self.timeToClear = time
        else:
            sys.exit("Error! This ambulance is already occupied")

    def setFree(self):
        if self.isBusy == True:
            self.isBusy = False
            self.timeToClear = 10000
        else:
            sys.exit("Error: This ambulance is already idle")

    def updateTime(self, time):
        if self.timeToClear >= time - 0.0001:
            self.timeToClear = self.timeToClear - time
        else:
            print self.station, self.timeToClear, time
            sys.exit("Error: Ambulance completion should be triggered first")









