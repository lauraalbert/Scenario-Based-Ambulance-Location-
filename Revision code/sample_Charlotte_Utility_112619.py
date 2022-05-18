########################################################################
# reads data from Hanover County Dataset and create call scenario samples
# updated: 03/22/2018
########################################################################

import sys
import csv
from gurobipy import *
import math
import random

# problem: if I import gurobi, somehow other path is forgotten
# (1) a path to external libraries (numpy, simpy...)
sys.path.append("C:\Python27\Lib\site-packages")
# (2) a path to all other libraries (ctypes, unittest..)
sys.path.append("C:\Python27\Lib")

import numpy as np
#from scipy.stats import rv_discrete

##### parameters hardcoded
#numALS = int(sys.argv[0]) # let's start with 18 ambs? or 12 should be better?
numALS = 3
numBLS = 3
numScenario = 200
distThreshold = 5 #3, 5
wH = 1.0
wL = 0.5
penalty = 0.5
scale = 1.0
numRep = 1
numeval = 500
pHigh = 0.2917 # update later to 0.4240
UHA = 1.0
UHB = float(sys.argv)/10 # 0.5# 0.0
ULA = 1.0
ULB = 1.0


##### run setting
seed = 44# 10, 44, 51
random.seed(seed)
doInitialize = True
ifRelax = True

print('UHB = ', UHB)  
print("Start. BLS = ", numBLS, " ALS = ", numALS )
print("penalty ", penalty )
print("BLS ", distThreshold," miles, ALS ", distThreshold," miles")
print("Probabilistic at 5miles")                                        #Stochastic
print(numScenario," Scenarios, t=7200, Seed # ", seed)

##### group calls by date AND timegroup
callLogReader = csv.reader(open('data/Charlotte_Weekdays12pm6pm_081218.csv','rU'))
callLogReader.next()# skip header
callLog = []
for row in callLogReader :
    callLog.append(row)
numDateTimeGroup = int(callLog[len(callLog) - 1][0]) + 1

callLogGrouped = {}
for i in range(0,numDateTimeGroup + 1):
    callLogGrouped[i] = []
for l in callLog:
    call = {}
    dateTimeGroup = int(l[0])
    #call['priority'] = 'H' if l[1] == '1' else 'L' # we use H:{1} L:{2,3}
    u = random.uniform(0,1)
    call['priority'] = 'H' if u < pHigh else 'L'
    call['location'] = int(l[1])
    call['arrivalTime'] = float(l[9])
    call['responseTime'] = float(l[7])
    call['serviceTime'] = float(l[8])
    callLogGrouped[dateTimeGroup].append(call)

##### read inputs from the Charlotte data
Rtimesreader = csv.reader(open('data/ResponseTime_Charlotte_050618.csv','rU'))
Rtimes = []
for row in Rtimesreader :
    Rtimes.append(row)
distancereader = csv.reader(open('data/MapInfo_Charlotte_050618.csv','rU'))
distance = []
for row in distancereader :
    distance.append(row)
Rprobreader = csv.reader(open('data/ResponseProbHigh_Charlotte_081218.csv','rU'))
RprobHigh = []
for row in Rprobreader:
    RprobHigh.append(row)
Rprobreader = csv.reader(open('data/ResponseProbLow_Charlotte_081218.csv','rU'))
RprobLow = []
for row in Rprobreader:
    RprobLow.append(row)


#indexes
numCustomer = len(Rtimes)-1
customer = range(1,numCustomer+1)
numStation = len(Rtimes[1])-1
station = range(1,numStation+1) # or below? then should redefine customer to be consistent. I think this way is easier
#station = Rtimes[0][1:]
timegroup = 2
# too many station? consider having less (e.g. aggregation). for now let's choose a random subset of some size.
random.shuffle(station)
station = station[10:40] # this is what I originally tested data for. But we also should test for full dataset.

#given data
tau = {}
dist = {}
respProbHigh = {}
respProbLow = {}
R ={}
Rh = {}
Rl = {}
for i in station :
    for j in customer :
        tau[i,j] = float(Rtimes[j][i])
        dist[i,j] = float(distance[j][i])
        respProbHigh[i,j] = 1.0 if dist[i,j] < 5 else 0
        respProbLow[i,j] = 1.0 if dist[i,j] < 5  else 0
                
        R[i,j] = 1.0 if dist[i,j] < 20  else 0#.90009
        #R[i,j] = 1 - (1/(1 + math.exp(5-(.5*dist[i,j])))) #1 - (1/(1 + math.exp(2.5-(.5*dist[i,j]))))
        R[i,j] = float(R[i,j])
        
        #Rh[i,j] = 1.0 if dist[i,j] < 5  else 0.0 #.90009
        #Rl[i,j] = 1.0 if dist[i,j] < 5  else 0.0 #.90009
        #stochastic distance
        Rh[i,j] = 1 - (1/(1 + math.exp(2.5-(.5*dist[i,j])))) #1 - (1/(1 + math.exp(2.5-(.5*dist[i,j]))))
        Rl[i,j] = 1 - (1/(1 + math.exp(2.5-(.5*dist[i,j])))) 
        Rl[i,j] = float(Rl[i,j])
        Rh[i,j] = float(Rh[i,j])
    
##### function for random call generation
def genCall() :

    serviceTime = {}
    arrivalTime = {}

    if doInitialize:
        # create calls passed from previous shift
        numOverCall, callHigh, callLow, location, nearStation, busyCall, serviceTime = genInitialCall()
        for c in range(numOverCall):
            arrivalTime[c] = 0.0
    else:
        # have to define these data types only if initialization is not included
        callHigh, callLow = [],[]
        location = {}
        nearStation = {}
        busyCall = {}
        numOverCall = 0

    l = random.randint(0,numDateTimeGroup) # pick a date and timegroup
    calls = callLogGrouped[l]
    numCall = len(calls)
    for c in range(numCall):
        if calls[c]['priority'] == 'H':
            callHigh.append(c+numOverCall)
        else:
            callLow.append(c+numOverCall)
        location[c+numOverCall] = calls[c]['location']
        arrivalTime[c+numOverCall] = calls[c]['arrivalTime']
        for i in station:
            # problem: when dist=0, response time avg is 0
            responseTime = tau[i,location[c+numOverCall]] if tau[i,location[c+numOverCall]] == 0 else random.expovariate(1/tau[i,location[c+numOverCall]])
            serviceTime[i,c+numOverCall] = responseTime + calls[c]['serviceTime']

    for c in range(numCall):
        nearStation[c+numOverCall] = []
        for i in station:
            if dist[i,location[c+numOverCall]] < distThreshold:
                nearStation[c+numOverCall].append(i)

        for i in station:
            busyCall[i,c+numOverCall] = []
            for d in range(numCall+numOverCall): # check for all calls earlier then c
                if arrivalTime[d] < arrivalTime[c+numOverCall] and arrivalTime[d] + serviceTime[i,d] > arrivalTime[c+numOverCall]:
                    busyCall[i,c+numOverCall].append(d)

    return numOverCall, numCall+numOverCall, callHigh, callLow, location, nearStation, busyCall,arrivalTime, serviceTime


def genInitialCall():
    #numCall, callHigh, callLow, location, nearStation, busyCall = genCall()
    # now pick of subset of calls that are incomplete by the end of timeline
    overCallList = []
    callHigh, callLow = [],[]
    location = {}
    nearStation = {}
    busyCall = {}
    serviceTime = {}
    arrivalTime = {}

    l = random.randint(0,numDateTimeGroup) # pick a date and timegroup
    calls = callLogGrouped[l]
    for c in range(len(calls)):
        if calls[c]['arrivalTime'] + calls[c]['responseTime'] > 60*12:
            overCallList.append(c)

    numOverCall = len(overCallList)

    for c1 in range(numOverCall):
        c = overCallList[c1]
        if calls[c]['priority'] == 'H':
            callHigh.append(c1)
        else:
            callLow.append(c1)
        location[c1] = calls[c]['location']
        arrivalTime[c1] = calls[c]['arrivalTime']

        for i in station:
            responseTime = tau[i,location[c1]] if tau[i,location[c1]] == 0 else random.expovariate(1/tau[i,location[c1]])

            # calculating service time : method (1) -- restart
            #serviceTime[i,c1] = responseTime + calls[c]['serviceTime']

            # calculating service time: method (2) -- take over
            overTime = calls[c]['arrivalTime'] + calls[c]['responseTime'] - 60*12
            serviceTime[i,c1] = max(responseTime, overTime) + calls[c]['serviceTime']

    for c1 in range(numOverCall):
        nearStation[c1] = []
        for i in station:
            if dist[i,location[c1]] < distThreshold:
                nearStation[c1].append(i)
        for i in station:
            busyCall[i,c1] = []
            for d in range(numOverCall):
                if arrivalTime[d] < arrivalTime[c1] and arrivalTime[d] + serviceTime[i,d] > arrivalTime[c1]:
                    busyCall[i,c1].append(d)

    return numOverCall, callHigh, callLow, location, nearStation, busyCall, serviceTime
            

# Test
#numOverCall, callHigh, callLow, location, nearStation, busyCall, serviceTime, arrivalTime = genInitialCall()
#numOverCall, numCall, callHigh, callLow, location, nearStation, busyCall, arrivalTime, serviceTime = genCall()
#print numOverCall, numCall, callHigh, callLow
#for c in range(numCall) : 
	#print 'call', c, 'from', location[c], 'arrived at', arrivalTime[c],'can be served by', nearStation[c]
	#print '     ', busyCall[5,c]#'takes', serviceTime[1,c]
	#print '     ', busyCall[60,c]#'takes', serviceTime[1,c]
	

# empirical distribution of overCall
#countOverCall = {}
#for c in range(10):
#    countOverCall[c] = 0
#for n in range(100000):
#    numOverCall, callHigh, callLow, location, nearStation, busyCall, serviceTime = genInitialCall()
#    countOverCall[numOverCall] += 1
#for c in range(10):
#    if countOverCall[c] > 0.1:
#        print c,":", countOverCall[c] / float(100000)


#avgNumCall = 0
#avgOverCall = 0
#for n in range(100000):
#    numOverCall, numCall, callHigh, callLow, location, nearStation, busyCall, arrivalTime, serviceTime = genCall()
#    avgNumCall += numCall
#    avgOverCall += numOverCall
#print avgNumCall / float(100000), avgOverCall / float(100000)

