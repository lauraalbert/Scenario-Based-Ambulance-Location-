########################################
# Simulation for SALT
# last update 01/29/19
########################################


##### library
import time as ti
import sys
import csv
from gurobipy import *
import random
import math

# problem: if I import gurobi, somehow other path is forgotton
# (1) a path to external libraries (numpy, simpy...)
sys.path.append("C:\Python27\Lib\site-packages")
# (2) a path to all other libraries (ctypes, unittest..)
sys.path.append("C:\Python27\Lib")

import numpy as np
#from scipy.stats import rv_discrete

#import sample_Hanover_122618 as inputs
import sample_Charlotte_112518 as inputs
import Ambulance
import Call
import Dispatcher



### some parameters
customer = inputs.customer
numStation = inputs.numStation
station = inputs.station
numScenario = inputs.numScenario

# MCLPP2 static solution
#ALSStations, BLSStations = [1,6,11], [12,14,15]

### 200 scenario SALT solution (updated 12/26/18)

# SALT1
#ALSStations, BLSStations = [1,6,14], [6,11,16] 

# SALT 2
#ALSStations, BLSStations = [1,6,14], [6,8,16]

# SALT3
#ALSStations, BLSStations = [1,6,14], [4,6,16]

# SALT 4
#ALSStations, BLSStations = [1,6,8], [6,14,16]

# SALT 5
#ALSStations, BLSStations = [7,10,14], [6,8,16]

# SALT 6
#ALSStations, BLSStations = [1,6,14], [6,15,16]

### sensitivity analysis
#ALSStations, BLSStations = [62, 4, 80], [72, 56, 42, 93, 27, 73, 70, 46, 96]
#ALSStations, BLSStations = [62, 58, 27, 79], [99, 72, 58, 42, 41, 73, 46, 96]
#ALSStations, BLSStations = [62, 42, 93, 73, 79], [16, 72, 42, 41, 70, 46, 96]
ALSStations, BLSStations = [42, 41, 93, 73, 70, 78], [72, 72, 62, 27, 46, 96]
#ALSStations, BLSStations = [62, 58, 42, 41, 46, 96, 80], [72, 93, 27, 73, 70]
#ALSStations, BLSStations = [42, 93, 27, 73, 70, 79, 46, 96], [72, 62, 41, 103]
#ALSStations, BLSStations = [16, 42, 42, 93, 73, 73, 70, 70, 46], [72, 79, 96]

# run a simulation using the data generated from generate()
def run(calls, ambulances):

    # calls are arrival events
    arrivals = calls
    # busy ambulances are service events
    services = []
    # set of completed calls.
    completions = []

    now = 0.0
    while len(arrivals) > 0 or len(services) > 0: # actually, we can stop when arrivals is empty
        #print '-----'
        #print int(now), ':', len(arrivals), 'calls left,', len(completions), 'ambulances busy'
        
        # check out the next event
        nextEventClock = checkNextEvent(arrivals, services, completions, ambulances, now)
        now = nextEventClock

    #print ' * Simulation is complete! * '
    return completions



def generate(ALSStations, BLSStations):
    # use input.genCall to create calls and arrange necessary inputs
    numOverCall, numCall, callHigh, callLow, locations, nearStations, busyCalls, arrivalTimes, serviceTimes = inputs.genCall()
    calls = []
    for c in range(numCall):
        priority = 'H' if c in callHigh else 'L'
        location = locations[c]
        arrivalTime = arrivalTimes[c]
        serviceTime = {}
        for i in station:
            serviceTime[i] = serviceTimes[i,c]
        calls.append(Call.Call(priority,location,arrivalTime,serviceTime))

    # generate ambulances
    ambulances = {}
    ambulances['A'], ambulances['B'] = [], []
    for i in ALSStations:
        ambulances['A'].append(Ambulance.Ambulance('A',i))
    for i in BLSStations:
        ambulances['B'].append(Ambulance.Ambulance('B',i))

    return calls, ambulances, len(callHigh), len(callLow)
   

    
def checkNextEvent(arrivals, services, completions, ambulances, now):

    nextArrivalClock, nextCompletionClock = 10000, 10000
    if len(arrivals) > 0:
        nextArrivalClock = arrivals[0].arrivalClock
    if len(services) > 0:
        nextCompletionClock = now + services[0].timeToClear
    
    if nextArrivalClock < nextCompletionClock:
        nextEventClock = nextArrivalClock
        updateTimeToClear(now, nextEventClock, services)

        #print 'call arrival'

        # pop a call and call dispatcher to decide which server to send
        currentCall = arrivals.pop(0)
        #serversToSend, isCovered = Dispatcher.sendTheClosest(ambulances, currentCall)
        serversToSend, isCovered = Dispatcher.sendTheClosestMatching(ambulances, currentCall)

        currentCall.evaluate(serversToSend, isCovered)

        # send server only if dispatcher did not return False
        if len(serversToSend) > 0:
            for server in serversToSend:
                #print 'send a server from', server.station

                # add the server to the list of services
                services.append(server)
                server.setBusy(currentCall.serviceTime[server.station]) # if serviceTime is station-specific, update this

            # and then also sort servers
            sortServers(services)
        else:
            #print 'this call is lost...'
            #sys.exit(0)
            pass

        # finally, add this call to the list of completions
        completions.append(currentCall)
    
    else:
        nextEventClock = nextCompletionClock
        updateTimeToClear(now, nextEventClock, services)

        #print 'service completion'
        
        # service completion
        serverToFree = services.pop(0)
        serverToFree.setFree()

    return nextEventClock


# sort busy servers in order of completion
def sortServers(services):
    services.sort(key=lambda x: x.timeToClear, reverse=False)


# update all busy ambulance timeToClear
def updateTimeToClear(now, nextEventClock, services):
    if len(services) > 0:
        for amb in services:
            amb.updateTime(nextEventClock - now)


# replicate runs and estimate system performance
def replicate(ALSStations, BLSStations):
    totalReward = 0.0
    totalCall = 0
    div = 0
    for r in range(numScenario):
        # generate scenario
        calls, ambulances, numCallHigh, numCallLow = generate(ALSStations, BLSStations)
        div += numCallHigh + 0.5*numCallLow
        # run
        completions = run(calls, ambulances)
        # analyze
        reward = analyze(completions)
        totalReward += reward

    return float(totalReward / div)
    
        

def analyze(completions):
    reward = 0.0
    for call in completions:
        if call.priority == 'H':
            reward = reward + call.reward
        else:
            reward = reward + 0.5 * call.reward
    return reward


def measureCI(numRep, ALSStations, BLSStations):
    rewards = np.zeros(numRep)
    for r in range(numRep):
        #print r,
        rewards[r] = replicate(ALSStations, BLSStations)

    reward_mean = np.mean(rewards)
    reward_std = np.std(rewards)
    reward_width = reward_std / math.sqrt(numRep)*1.96

    print 'mean reward:', reward_mean
    print 'standard deviation:', reward_std
    print 'confidence interval:', reward_mean - reward_width, reward_mean + reward_width



starttime = ti.time()

measureCI(30, ALSStations, BLSStations)

endtime = ti.time()

print ALSStations, BLSStations
print 'time elapsed:', endtime - starttime
print inputs.numALS, inputs.numBLS





        
