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

#NOTE: when changing Input file, you also need to change dispatcher and call .py files
import sample_Hanover_Utlity_112519 as inputs
#import sample_Charlotte_Utility_112619 as inputs

import Ambulance
import Call
import Dispatcher

### some parameters
customer = inputs.customer
numStation = inputs.numStation
station = inputs.station
numScenario = inputs.numScenario
UHB = inputs.UHB
R = inputs.Rh

numBLS=inputs.numBLS
numALS=inputs.numALS
penalty=inputs.penalty
distThreshold =inputs.distThreshold
seed = inputs.seed

f = str(UHB) + "UHB_Hanover_DetSol_ProbSimulations_SeedSol_44.txt"
sys.stdout = open(str(f),'w')
  
print("START. BLS = ", numBLS, " ALS = ", numALS )
print("penalty ", penalty )
print("BLS ", distThreshold," miles, ALS ", distThreshold," miles")
print(numScenario," Scenarios, t=7200, Eval_Seed # ", seed, "Solution Seed # 44")
      

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

########## sensitivity analysis for probabilistic utlity 6ALS 6BLS - Charlotte
#ALSStations, BLSStations = [57, 52, 96, 62, 88, 72],	[35, 52, 62, 41, 72, 83] #UHB=0.0
#ALSStations, BLSStations =[44, 57, 52, 96, 72, 91],	[35, 62, 88, 41, 83, 83] #UHB=0.1
#ALSStations, BLSStations = [57, 52, 52, 96, 72, 72],	[35, 44, 57, 84, 88, 83] #UHB=0.2
#ALSStations, BLSStations =[15, 52, 52, 84, 96, 72],	 [44, 57, 80, 41, 72, 83] #UHB=0.3
#ALSStations, BLSStations =[52, 52, 62, 62, 72, 72],	[57, 57, 96, 96, 88, 41] #UHB=0.4
#ALSStations, BLSStations =[29, 63, 52, 80, 41, 41],	[74, 15, 57, 96, 72, 72] #UHB=0.5

########### sensitivity analysis for varying utlity 3ALS 3BLS - Hannover
###Probablistic Travel Time
#ALSStations, BLSStations =[7, 8, 16],	[1,6,14] #UHB=0.0, 0.1, 0.3, 0.4, 0.5
#ALSStations, BLSStations =[1, 7, 8],	[6,14,16] #UHB=0.2
###Deterministic Travel Time
#ALSStations, BLSStations =[1, 7, 8],	[6,14,16] #UHB=0.0, 0.1, 0.2, 0.3, 0.4, 0.5 <- solutions didnt change with utility

##########Evaluating several seeds: evaluating solutions seeds 10,18,23,39,51,44 with seed 64
###Probablistic Travel Time
#ALSStations, BLSStations = [1,7,8], [6,14,16] #seed 10 & 18
#ALSStations, BLSStations = [7,13,16], [1,8,14] #seed 23
#ALSStations, BLSStations = [6,7,16], [1,8,14] #seed 39
#ALSStations, BLSStations = [7,8,16], [1,6,14] #seed 51 & 44 
###Deterministic Travel Time
#ALSStations, BLSStations = [1, 6, 14],	[7, 10, 11] #seed 10,23,39,51
#ALSStations, BLSStations = [1, 6, 14],	[7, 11, 16] #seed 18
ALSStations, BLSStations = [1, 7, 8],	[6, 14, 16] #seed 44



print("ALS Stations",ALSStations,"BLS Stations", BLSStations)

# run a simulation using the data generated from generate()
def run(calls, ambulances):

    # calls are arrival events
    arrivals = calls
    # busy ambulances are service events
    services = []
    # set of completed calls.
    completions = []
    #Response time
    RTIME= []

    now = 0.0
    while len(arrivals) > 0 or len(services) > 0: # actually, we can stop when arrivals is empty
       # print '-----'
       # print int(now), ':', len(arrivals), 'calls left,', len(completions), 'ambulances busy'
        
        # check out the next event
        nextEventClock = checkNextEvent(arrivals, services, completions, ambulances, now, RTIME)
        now = nextEventClock

    #print ' * Simulation is complete! * '
    return completions, RTIME



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
   

    
def checkNextEvent(arrivals, services, completions, ambulances, now, RTIME):

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
        #        print 'send a server from', server.station

                # add the server to the list of services
                services.append(server)
                server.setBusy(currentCall.serviceTime[server.station]) # if serviceTime is station-specific, update this

            # and then also sort servers
            sortServers(services)
        else:
         #   print 'this call is lost...'
            #sys.exit(0)
            pass

        # finally, add this call to the list of completions
        completions.append(currentCall)
        maxR=0    
        if len(serversToSend) > 0:
            for server in serversToSend:
                if R[server.station, currentCall.location] > maxR:
                    maxR= R[server.station, currentCall.location]
        RTIME.append(maxR)
    
    else:
        nextEventClock = nextCompletionClock
        updateTimeToClear(now, nextEventClock, services)

       # print 'service completion'
        
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
        div += numCallHigh + UHB*numCallLow
        # run
        completions, RTIME = run(calls, ambulances)
        # analyze
        reward = analyze(completions, RTIME)
        totalReward += reward

    return float(totalReward / div)
    
        

def analyze(completions, RTIME):
    reward = 0.0
    for call_index, call in enumerate(completions):
        if call.priority == 'H':
            reward = reward + call.reward * RTIME[call_index]
        else:
            reward = reward + UHB * call.reward*RTIME[call_index]
    return reward


def measureCI(numRep, ALSStations, BLSStations):
    rewards = np.zeros(numRep)
    for r in range(numRep):
        print r,
        rewards[r] = replicate(ALSStations, BLSStations)
    reward_mean = np.mean(rewards)
    reward_std = np.std(rewards)
    reward_width = reward_std / math.sqrt(numRep)*1.96
    print 'rewards for runs:', rewards
    print 'mean reward:', reward_mean
    print 'standard deviation:', reward_std
    print 'confidence interval:', reward_mean - reward_width, reward_mean + reward_width



starttime = ti.time()

measureCI(30, ALSStations, BLSStations)

endtime = ti.time()

print ALSStations, BLSStations
print 'time elapsed:', endtime - starttime
print inputs.numALS, inputs.numBLS



        
