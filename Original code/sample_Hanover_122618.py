########################################################################
# reads data from Hanover County Dataset and create call scenario samples
# updated: 12/04/2018
# new feature: now initialize based on the 'previous' time period samples
########################################################################

import sys
import csv
from gurobipy import *
import math
import random

# problem: if I import gurobi, somehow other path is forgotton
# (1) a path to external libraries (numpy, simpy...)
sys.path.append("C:\Python27\Lib\site-packages")
# (2) a path to all other libraries (ctypes, unittest..)
sys.path.append("C:\Python27\Lib")

import numpy as np
#from scipy.stats import rv_discrete

##### parameters hardcoded
numALS = 3 
numBLS = 3
numScenario = int(sys.argv[1])
distThreshold = 5 #3, 5: 5 mi = 9 min
wH = 1.0
wL = 0.5
penalty = 0.5
numRep = 15
numeval = 500
UHA = 1.0
UHB = 0.5# 0.0
ULA = 1.0
ULB = 1.0


##### run setting
doInitialize = True
ifRelax = True
seed = 10# 10, 44, 51
random.seed(seed)


##### group calls by date AND timegroup
callLogReader = csv.reader(open('data/Hanover_Weekdays6am6pm_050118.csv','rU'))
callLogReader.next()# skip header
callLog = []
for row in callLogReader :
    callLog.append(row)
numDateTimeGroup = int(callLog[len(callLog) - 1][0]) + 1


callLogGrouped = {}
callLogGrouped_prev = {}
for i in range(0,numDateTimeGroup + 1):
    callLogGrouped[i] = []
    callLogGrouped_prev[i] = []
for l in callLog:
    call = {}
    dateTimeGroup = int(l[0])
    call['priority'] = 'H' if l[1] == '1' else 'L' # we use H:{1} L:{2,3}
    call['location'] = int(l[2])
    call['arrivalTime'] = float(l[3])
    call['responseTime'] = float(l[4])
    call['sceneTime'] = float(l[5])
    call['transportTime'] = float(l[6])
    if int(l[22]) < 12:
        callLogGrouped_prev[dateTimeGroup].append(call)
    else:
        callLogGrouped[dateTimeGroup].append(call)

##### read inputs from the Hanover county data
Rtimesreader = csv.reader(open('data/ResponseTime_Hanover_031918.csv','rU'))
Rtimes = []
for row in Rtimesreader :
    Rtimes.append(row)
distancereader = csv.reader(open('data/MapInfo_Hanover_031918.csv','rU'))
distance = []
for row in distancereader :
    distance.append(row)
Rprobreader = csv.reader(open('data/ResponseProbHigh_Hanover_062418.csv','rU'))
RprobHigh = []
for row in Rprobreader:
    RprobHigh.append(row)
Rprobreader = csv.reader(open('data/ResponseProbLow_Hanover_062418.csv','rU'))
RprobLow = []
for row in Rprobreader:
    RprobLow.append(row)

#indexes
numCustomer = len(Rtimes)-1
customer = range(1,numCustomer+1)
numStation = len(Rtimes[1])-1
station = range(1,numStation+1)
timegroup = 2

#given data
tau = {}
dist = {}
respProbHigh = {}
respProbLow = {}
for i in station :
    for j in customer :
        tau[i,j] = float(Rtimes[j][i])
        dist[i,j] = float(distance[j][i])
        respProbHigh[i,j] = 1.0 if dist[i,j] < 5 else 0
        respProbLow[i,j] = 1.0 if dist[i,j] < 5  else 0
        #respProbHigh[i,j] = float(RprobHigh[j][i])
        #respProbLow[i,j] = float(RprobLow[j][i])

       
##### function for random call generation
def genCall() :

    l = random.randint(0,numDateTimeGroup) # use this same l to initialize
    #l = 2

    serviceTime = {}
    arrivalTime = {}

    if doInitialize:
        # create calls passed from previous shift
        numOverCall, callHigh, callLow, location, nearStation, busyCall, serviceTime = genInitialCall(l)
        for c in range(numOverCall):
            arrivalTime[c] = 0.0
    else:
        # have to define these data types only if initialization is not included
        callHigh, callLow = [],[]
        location = {}
        nearStation = {}
        busyCall = {}
        numOverCall = 0

    calls = callLogGrouped[l]
    numCall = len(calls)
    for c in range(numCall):
        if calls[c]['priority'] == 'H':
            callHigh.append(c+numOverCall)
        else:
            callLow.append(c+numOverCall)
        location[c+numOverCall] = calls[c]['location']
        arrivalTime[c+numOverCall] = calls[c]['arrivalTime'] - 60*6
        for i in station:
            # problem: when dist=0, response time avg is 0
            responseTime = tau[i,location[c+numOverCall]] if tau[i,location[c+numOverCall]] == 0 else random.expovariate(1/tau[i,location[c+numOverCall]])
            serviceTime[i,c+numOverCall] = responseTime + calls[c]['sceneTime'] + calls[c]['transportTime']

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
    
    return numOverCall, numCall+numOverCall, callHigh, callLow, location, nearStation, busyCall, arrivalTime, serviceTime


def genInitialCall(l):
    # pick subset of calls that are incomplete by the end of timeline
    overCallList = []
    callHigh, callLow = [],[]
    location = {}
    nearStation = {}
    busyCall = {}
    serviceTime = {}
    arrivalTime = {}

    calls = callLogGrouped_prev[l]
    for c in range(len(calls)):
        if calls[c]['arrivalTime'] + calls[c]['responseTime'] + calls[c]['sceneTime'] > 60*6:
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
            #serviceTime[i,c1] = responseTime + calls[c]['sceneTime'] + calls[c]['transportTime']

            # calculating service time: method (2) -- take over
            overTime = calls[c]['arrivalTime'] + calls[c]['responseTime'] + calls[c]['sceneTime'] - 60*6
            serviceTime[i,c1] = max(responseTime, overTime) + calls[c]['transportTime']

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

    # Let's check if call is over first,
    # and then implement two different ways

    #print overCallList

    return numOverCall, callHigh, callLow, location, nearStation, busyCall, serviceTime
            

### Test
#numCall, callHigh, callLow, location, nearStation, busyCall, serviceTime = genInitialCall()
#numOverCall, numCall, callHigh, callLow, location, nearStation, busyCall, arrivalTime = genCall()
#print numOverCall, numCall, callHigh, callLow
#for c in range(numCall) : 
#	print 'call', c, 'from', location[c], 'arrived at', arrivalTime[c],'can be served by', nearStation[c], busyCall[1,c]


### empirical distribution of overcall and numCall
#countCall = {}
#for c in range(10):
#    countCall[c] = 0
#for n in range(100000):
#    numOverCall, numCall, callHigh, callLow, location, nearStation, busyCall, arrivalTime, serviceTime = genCall()
#    countCall[numOverCall] += 1
#for c in range(10):
#    if countCall[c] > 0.1:
#        print c,":", countCall[c] / float(100000)

#sys.exit(0)

#avgNumCall = 0
#avgOverCall = 0
#for n in range(1000000):
#    numOverCall, numCall, callHigh, callLow, location, nearStation, busyCall, arrivalTime, serviceTime = genCall()
#    avgNumCall += numCall
#    avgOverCall += numOverCall
#print avgNumCall / float(1000000), avgOverCall / float(1000000)
