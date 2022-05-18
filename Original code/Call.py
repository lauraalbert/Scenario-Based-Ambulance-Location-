########################################
# Simulation for SALT -- Ambulance
# last update 09/06/18
########################################

#import sample_Hanover_122618 as inputs
import sample_Charlotte_112518 as inputs



class Call():

    # constructor
    def __init__(self, priority, location, arrivalTime, serviceTime):
        self.priority = priority
        self.location = location
        self.arrivalClock = arrivalTime
        self.serviceTime = serviceTime
        self.reward = 0.0
        self.serversToSend = []

    def evaluate(self, serversToSend, isCovered):
        self.serversToSend = serversToSend
        if len(serversToSend) == 0:
            self.reward = - inputs.penalty
        elif isCovered:
            self.reward = 1.0
        else:
            self.reward = 0.0
            
            
        

        











