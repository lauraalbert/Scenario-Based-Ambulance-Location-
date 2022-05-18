# -*- coding: utf-8 -*-
"""
Created on Sat May 16 20:19:37 2020

@author: vmwhite
"""

########################################################################
# Solve the Mean Value Problem and Evaluate the VSS
#Let's assume all bundel of calls are equally liklely than any one call could be the average bundle?
#OR find the average number of  high and low calls in a bundle 
# updated: 09/04/2018

#repeat the following for each seed:
    #1.) solve mean value problem
        #A.) Determine "average" call bundle
        #B.) Create and solve the mean value problem using the "average" bundle of calls.
        #C.) Fix locaition solutions in SP and solve under 200 scenarios
    #2.) Use VSS solutions that are already solved
    #3.) calculate VSS 

########################################################################

##### library
import sys
import csv
from gurobipy import *
import math
import random
import time as ti


# (1) a path to external libraries (numpy, simpy...)
sys.path.append("C:\Python27\Lib\site-packages")
# (2) a path to all other libraries (ctypes, unittest..)
sys.path.append("C:\Python27\Lib")

import sample_Hanover_122618 as input

from sample_Hanover_122618 import genCall

#from SALT_DEFL_012419 import solve
starttime = ti.time()

##### parameters hardcoded
numServer = {'A':input.numALS, 'B':input.numBLS}
numScenario = input.numScenario
scenario = range(1,numScenario + 1)
distThreshold = input.distThreshold
customer = input.customer
numStation = input.numStation
station = input.station
wH = input.wH
wL = input.wL
penalty = input.penalty
serverType = ['A', 'B']
UHA, UHB, ULA, ULB = input.UHA, input.UHB, input.ULA, input.ULB
respProbHigh, respProbLow = input.respProbHigh, input.respProbLow
ifRelax = input.ifRelax
callLog = input.callLog
seed = input.seed
doInitialize = input.doInitialize


#1.) Solving the Mean Value Problem
#A.) Determining the Average call bundle
##### Calcualting CDF of a call arrival probability per location and priority  #########
def read_input_for_lambdas():

    ##### read inputs from the Hanover county data
    distancefile = open('data/distance_Hanover_031918.csv','rU')
    distancereader = csv.reader(distancefile)
    distance = []
    for row in distancereader :
        distance.append(row)
    
    responsefile = open('data/ResponseTime_Hanover_031918.csv','rU')
    responsereader = csv.reader(responsefile)
    responsetable = []
    for row in responsereader :
        responsetable.append(row)
        
    dist = {}
    response = {}
    for i in station : 
        for j in customer : 
            dist[i,j] = float(distance[j][i])
            response[i,j] = float(responsetable[j][i])

    # for demand, read from the call log
    demand_high, demand_low = {}, {} 
    demand_high_rate, demand_low_rate = {},{}
    cum_demand_high, cum_demand_low = [], []
   
    transportTime = {}
    avg_transportTime ={}

    sceneTime_high, sceneTime_low =0.00,0.00
    avg_sceneTime =[]
    
    tot_cust=0
    avg_tt_location=0.0
    
    total_high,total_low = 0,0 # we need to rescale the data between 0 and 1 to get a distribution
    for j in customer:
        demand_high[j], demand_low[j] = 0, 0 #0, 0
        demand_high_rate[j],demand_low_rate[j] = 0.00,0.00
        transportTime[j], avg_transportTime[j]= 0.00,0.00
    for l in callLog:
        location = int(l[2])
        transportTime[location] += float(l[6])
        if l[1] == '1':
            demand_high[location] += 1
            total_high += 1
            sceneTime_high += float(l[5]) #to find avg scene time per call type
        else:
            demand_low[location] += 1
            total_low += 1
            sceneTime_low += float(l[5])
    
    for j in customer:
         if float(demand_high[j]+demand_low[j]) !=0:
            avg_transportTime[j] = float(transportTime[j])/float(demand_high[j]+demand_low[j]) # to find average transport time per customer location 
         if avg_transportTime[j] != 0:
             tot_cust += 1
             avg_tt_location +=avg_transportTime[j]
    avg_tt_location = avg_tt_location/float(tot_cust)
    
    for j in customer:
        if demand_high[j]==0:
            demand_high[j]=1
            total_high += 1
            avg_transportTime[j]=avg_tt_location
        if  demand_low[j]==0:
            demand_low[j] = 1
            total_low += 1
            avg_transportTime[j]=avg_tt_location
    #print total_high, total_low 
    for j in customer:
        demand_high_rate[j] = float(demand_high[j])/float(total_high)
        demand_low_rate[j] = float(demand_low[j])/float(total_low)
    sceneTime ={}
    sceneTime["H"] = float(sceneTime_high)/float(total_high)
    sceneTime["L"] = float(sceneTime_low)/float(total_low)
    avg_sceneTime.append(sceneTime)
    accum_high = 0
    accum_low = 0
    for j in customer:
        accum_high += demand_high_rate[j]
        accum_low += demand_low_rate[j]
        cum_demand_high.append(accum_high)
        cum_demand_low.append(accum_low)
        #finding first arrival times
    arrival_time = {}
    num_arrivals = {}
    arrival_day = -1

    for c in callLog:

        if arrival_day != int(c[0]):
            call_idx = 0
        if call_idx not in arrival_time:
            arrival_time[call_idx] = 0
            num_arrivals[call_idx] = 0
        arrival_time[call_idx] += int(c[3])
        num_arrivals[call_idx] += 1
        arrival_day = int(c[0])
        call_idx += 1

    for idx,_ in enumerate(arrival_time):
        arrival_time[idx] = float(arrival_time[idx]) / num_arrivals[idx]
        

    return dist, response, cum_demand_high, cum_demand_low, avg_transportTime,avg_sceneTime, arrival_time


####### Printing CDF of a call arrival probabilty at a given customer location ###########
distance, response, cum_demand_high, cum_demand_low, avg_transportTime,avg_sceneTime, arrival_time = read_input_for_lambdas()
print("Customer, CDF_high, CDF_low, Transport_Time")
for i, j in enumerate(customer):
    print "%d %f %f %f" %(j, cum_demand_high[i], cum_demand_low[i],avg_transportTime[j])
################## Print the average Arrival times of calls ###########
print '----------------------------------------'
print("Average Call Arrival Times")
for idx, i in enumerate(arrival_time):
    print(idx, arrival_time[idx])
################################ Average sceneTime for a high call and low call ###############################
print '----------------------------------------'
print("Average Scene times for (High, Low) call")
print avg_sceneTime
############# Determining the average number of High and Low calls in the avereage call bundle ####################

avgNumCall = 0
avgOverCall = 0
avgCallHigh = 0
avgCallLow = 0
total = 1000

numOverCall = {}
numCall = {}
numCallTotal = 0
callHigh = {}
numHighCall = 0
callLow = {}
numLowCall = 0
location = {}
nearStation = {}
busyCall = {}
arrivalTime = {}
serviceTime = {}
numHighCallIn = 0
numLowCallIn = 0

for n in range(total):
    numOverCall[n], numCall[n], callHigh[n], callLow[n], location[n], nearStation[n], busyCall[n], arrivalTime[n], serviceTime[n] = genCall()
    numCallTotal += numCall[n]
    for c in callHigh[n] : 
        numHighCall += 1
        if c >= numOverCall[n]:
            numHighCallIn += 1
    for c in callLow[n] : 
        numLowCall += 1
        if c >= numOverCall[n]:
            numLowCallIn += 1
            
MeanNumCalls=float(numCallTotal)/float(total)
MeanNumHigh=float(numHighCall)/float(total)
MeanNumLow=float(numLowCall)/float(total)

print '----------------------------------------'
print 'Number of Scenarios:', numScenario
print 'Total number of calls:', MeanNumCalls,'(Mean High Calls:',MeanNumHigh,', Mean Low Calls:',MeanNumLow,')'



##### function for random call generation
def VSSgenCall(MeanNumHigh,MeanNumLow,dist) :

    l = 1# use this same l to initialize
    
    serviceTime = {}
    arrivalTime = {}

    if doInitialize:
        # create calls passed from previous shift
        numOverCall, callHigh, callLow, location, nearStation, busyCall, serviceTime = VSSgenInitialCall(MeanNumCalls, arrival_time, dist)
        for c in range(numOverCall):
            arrivalTime[c] = 0.0
    else:
        # have to define these data types only if initialization is not included
        callHigh, callLow = [],[]
        location = {}
        nearStation = {}
        busyCall = {}
        numOverCall = 0

    ###### Randomly generating the average call Location based on the CDF of call location arrival #####
    #### These will change when the seed changes #####
    MeanCallLocations = []
    
    rand_calls_high = [random.random() for _ in range(int(round(MeanNumHigh)))]
    rand_calls_low = [random.random() for _ in range(int(round(MeanNumLow)))]
 #   print (rand_calls_low)
    for i in rand_calls_high:
        for call_ind, j in enumerate(cum_demand_high):
            if i < j:
                call = {}
                call["location"] = (call_ind +1)
                call["priority"] = "H"
                call["sceneTime"] = avg_sceneTime[0]["H"]
                call["transportTime"] =avg_transportTime[call_ind+1]
                MeanCallLocations.append(call)
                break
            
    for i in rand_calls_low:
        for call_ind, j in enumerate(cum_demand_low):
            if i < j:
                call = {}
                call["location"] = (call_ind + 1)
                call["priority"] = "L"
                call["sceneTime"] = avg_sceneTime[0]["L"]
                call["transportTime"] =avg_transportTime[call_ind+1]
                MeanCallLocations.append(call)
                break
    print("Mean Value Call Bundle Scenario Locations of (High, Low) priority:")
 #   print(MeanCallLocations)
    random.shuffle(MeanCallLocations)
    print(MeanCallLocations)    
    
    numCall = len(MeanCallLocations)
    for c in range(numCall):
        if MeanCallLocations[c]['priority'] == 'H':
            callHigh.append(c+numOverCall)
        else:
            callLow.append(c+numOverCall)
        location[c+numOverCall] = MeanCallLocations[c]['location']
        arrivalTime[c+numOverCall] =  arrival_time[c] #60*6
        for i in station:
            # problem: when dist=0, response time avg is 0
            responseTime = dist[i,location[c+numOverCall]] if dist[i,location[c+numOverCall]] == 0 else random.expovariate(1/dist[i,location[c+numOverCall]])
            serviceTime[i,c+numOverCall] = responseTime + MeanCallLocations[c]['sceneTime'] + MeanCallLocations[c]['transportTime']

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

#on average there is 0.75 calls from the previous run, let's round this to 1 low priority call
def VSSgenInitialCall(MeanNumCalls,arrival_time, dist):
    # pick subset of calls that are incomplete by the end of timeline

    callHigh, callLow = [],[]
    location = {}
    nearStation = {}
    busyCall = {}
    serviceTime = {}
    arrivalTime = {}

    numOverCall = 1

    for c1 in range(numOverCall):
  #      if calls[c]['priority'] == 'H':
  #          callHigh.append(c1)
  #      else:
        callLow.append(c1)
        i = random.random()
        #print(i)
        for call_ind, j in enumerate(cum_demand_low):
            if i < j:
                location[c1] = call_ind +1
        arrivalTime[c1] = arrival_time[int(round(MeanNumCalls)-1)]

        for i in station:
            responseTime = dist[i,location[c1]] if dist[i,location[c1]] == 0 else random.expovariate(1/dist[i,location[c1]])

            # calculating service time : method (1) -- restart
            #serviceTime[i,c1] = responseTime + calls[c]['sceneTime'] + calls[c]['transportTime']

            # calculating service time: method (2) -- take over
            overTime = arrivalTime[c1] + responseTime + avg_sceneTime[0]["L"] - 60*6
            serviceTime[i,c1] = max(responseTime, overTime) + avg_transportTime[location[c1]]

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
          
#numOverCall, callHigh, callLow, location, nearStation, busyCall, serviceTime = VSSgenInitialCall(MeanNumCalls, arrival_time, distance)  
#print("Initial Call")
numOverCall1, numCallnumOverCall1, callHigh1, callLow1, location1, nearStation1, busyCall1, arrivalTime1, serviceTime1 = VSSgenCall(MeanNumHigh,MeanNumLow,distance) 
#print "numOverCall", numOverCall, "numCall+Numovercall", numCallnumOverCall, "Call High", callHigh, "Call Low", callLow, "Location", location, "Nearstation", nearStation,"BusyCall", busyCall, "arrivaltime", arrivalTime, "serviceTime",serviceTime

##### call generation
callHigh, callLow = {},{}
location, nearStation, busyCall = {},{},{}
arrivalTime, serviceTime = {}, {}
numOverCall, numCall = {}, {}
numCallTotal, numHighCall, numLowCall, numHighCallIn, numLowCallIn = 0,0,0,0,0
for s in scenario:
    numOverCall[s], numCall[s], callHigh[s], callLow[s], location[s], nearStation[s], busyCall[s], arrivalTime[s], serviceTime[s] = numOverCall1, numCallnumOverCall1, callHigh1, callLow1, location1, nearStation1, busyCall1, arrivalTime1, serviceTime1 

    numCallTotal += numCall[s]
    for c in callHigh[s] : 
        numHighCall += 1
        if c >= numOverCall[s]:
            numHighCallIn += 1
    for c in callLow[s] : 
        numLowCall += 1
        if c >= numOverCall[s]:
            numLowCallIn += 1
print '----------------------------------------'
print 'Number of Scenarios:', numScenario
print 'Total number of calls:', numCallTotal,'(',numHighCall,',',numLowCall,')'


# 1 B.) Create and solve the mean value problem using the "average" bundle of calls.
##### Subproblem, linearly relaxed    
def subproblem(opt,numOverCall, numCall, callHigh, callLow, location, nearStation, busyCall):

    sub = Model('SALT Subproblem')
    sub.params.logtoconsole = 0
    sub.modelsense = GRB.MAXIMIZE

    ### subproblem variables
    y = {} # dispatch
    for i in station:
        for p in serverType:
            for c in range(numCall):
                y[i,p,c] = sub.addVar(vtype = GRB.CONTINUOUS)
    z = {} # cover
    zA = {} # cover, high, by ALS
    zB = {} # cover, high, by BLS + ALS
    for c in callHigh:
        z[c] = sub.addVar(obj = wH, vtype = GRB.CONTINUOUS)
        zA[c] = sub.addVar(vtype = GRB.CONTINUOUS)
        zB[c] = sub.addVar(vtype = GRB.CONTINUOUS)
    for c in callLow:
        z[c] = sub.addVar(obj = wL, vtype = GRB.CONTINUOUS)
        
    g = {} # lost call
    for c in range(numCall):
        g[c] = sub.addVar(obj = -penalty, vtype = GRB.CONTINUOUS)
    sub.update()

    ### subproblem constraints
    # cannot dispatch more than deployed.
    c_dispatch = {}
    for i in station : 
        for p in serverType : 
            for c in range(numCall) : 
                c_dispatch[i,p,c] = sub.addConstr(y[i,p,c] + quicksum(y[i,p,d] for d in busyCall[i,c]) <= opt[i,p])

    # low priority calls can be covered by nearby server of any type.
    c_coverLow = {}
    for c in callLow : 
        c_coverLow[c] = sub.addConstr(z[c] - quicksum(quicksum(y[i,p,c] for i in nearStation[c]) for p in serverType) <= 0)

    # high priority calls can be covered either (1) nearby ALS or by (2) nearby BLS and faraway ALS.
    c_coverHigh1 = {}
    c_coverHigh2A = {}
    c_coverHigh2B = {}
    c_coverHigh = {}
    for c in callHigh : 
        c_coverHigh1[c] = sub.addConstr(zA[c] - quicksum(y[i,'A',c] for i in nearStation[c]) <= 0)
        c_coverHigh2A[c] = sub.addConstr(zB[c] - quicksum(y[i,'B',c] for i in nearStation[c]) <= 0)
        #c_coverHigh2B[c] = sub.addConstr(zB[c] - quicksum(y[i,'A',c] for i in station) <= 0)
        # new constraint coverHigh2B that prevents double-counting behavior
        c_coverHigh2B[c] = sub.addConstr(zB[c] - quicksum(y[i,'A',c] for i in (k for k in station if k not in nearStation[c])) <= 0)
        c_coverHigh[c] = sub.addConstr(z[c] - zA[c] - zB[c] <= 0)

    # penalize calls that are lost (no server is dispatched)
    c_loss = {}
    for c in range(numCall) : 
        c_loss[c] = sub.addConstr(0 - g[c] - quicksum(quicksum(y[i,p,c] for i in station) for p in serverType) <= -1)

    # need to add upper bounds for all (originally) binary variables
    c_y = {}
    for i in station:
        for p in serverType:
            for c in range(numCall):
                c_y[i,p,c] = sub.addConstr(y[i,p,c] <= 1)
    c_z = {}
    for c in range(numCall):
        c_z[c] = sub.addConstr(z[c] <= 1)

    c_zA, c_zB = {}, {}
    for c in callHigh:
        c_zA[c] = sub.addConstr(zA[c] <= 1)
        c_zB[c] = sub.addConstr(zB[c] <= 1)

    c_g = {}
    for c in range(numCall):
        c_g[c] = sub.addConstr(g[c] <= 1)

    sub.update()

    sub.optimize()

    # this part is for benders cut
    rhs = 0.0
    for c in range(numCall):
        rhs += c_z[c].Pi + c_g[c].Pi - c_loss[c].Pi
    for c in callHigh:
        rhs += c_zA[c].Pi + c_zB[c].Pi
        

    xcoef = {}
    for i in station:
        for p in serverType:
            for c in range(numCall):
                xcoef[i,p,c] = c_dispatch[i,p,c].Pi
                rhs += c_y[i,p,c].Pi

    return sub.objVal, rhs, xcoef



##### Double check: reevaluate the optimal solution

### Solve second-stage problem to reevaluate solutions from linear relaxed problem

def solveSSP_Int(opt, numOverCall, numCall, callHighs, callLows, locations, nearStations, busyCalls) : 

    sub = Model("Subproblem")
    sub.modelsense = GRB.MAXIMIZE
    #sub.params.logtoconsole = 0
    sub.params.outputflag = 0

    ### subproblem variables

    y = {} # dispatch	
    for i in station : 
        for p in serverType : 
            for c in range(numCall) : 
                y[i,p,c] = sub.addVar(vtype = GRB.BINARY)				
    z = {} # cover
    zA = {} # cover, high, by ALS
    zB = {} # cover, high, by BLS + ALS
    for c in callHighs : 
        z[c] = sub.addVar(obj = wH, vtype = GRB.BINARY)
        zA[c] = sub.addVar(vtype = GRB.BINARY)       
        zB[c] = sub.addVar(vtype = GRB.BINARY)
    for c in callLows : 
        z[c] = sub.addVar(obj = wL, vtype = GRB.BINARY)

    g = {} # lost call	
    for c in range(numCall) : 
        g[c] = sub.addVar(obj = -penalty, vtype = GRB.BINARY)
    sub.update()

    ### subproblem constraints
            
    # cannot dispatch more than deployed.
    c_dispatch = {}
    for i in station : 
        for p in serverType : 
            for c in range(numCall) : 
                c_dispatch[i,p,c] = sub.addConstr(y[i,p,c] + quicksum(y[i,p,d] for d in busyCalls[i,c]) <= opt[i,p])

    # low priority calls can be covered by nearby server of any type.
    c_coverLow = {}
    for c in callLows : 
        c_coverLow[c] = sub.addConstr(z[c] - quicksum(quicksum(y[i,p,c] for i in nearStations[c]) for p in serverType) <= 0)

    # high priority calls can be covered either (1) nearby ALS or by (2) nearby BLS and faraway ALS.
    c_coverHigh1 = {}
    c_coverHigh2A = {}
    c_coverHigh2B = {}
    c_coverHigh = {}
    for c in callHighs : 
        c_coverHigh1[c] = sub.addConstr(zA[c] - quicksum(y[i,'A',c] for i in nearStations[c]) <= 0)
        c_coverHigh2A[c] = sub.addConstr(zB[c] - quicksum(y[i,'B',c] for i in nearStations[c]) <= 0)
        #c_coverHigh2B[c] = sub.addConstr(zB[c] - quicksum(y[i,'A',c] for i in station) <= 0)
        # new constraint coverHigh2B that prevents double-counting behavior
        c_coverHigh2B[c] = sub.addConstr(zB[c] - quicksum(y[i,'A',c] for i in (k for k in station if k not in nearStations[c])) <= 0)
        c_coverHigh[c] = sub.addConstr(z[c] - zA[c] - zB[c] <= 0)

    # penalize calls that are lost (no server is dispatched)
    c_loss = {}
    for c in range(numCall) : 
            c_loss[c] = sub.addConstr(0 - g[c] - quicksum(quicksum(y[i,p,c] for i in station) for p in serverType) <= -1)

    #### TODO set constraints for # of dispatches for test purpose.. see how the answer differs.
    c_test1, c_test2, c_test3 = {}, {}, {}
    for c in callLows:
        c_test1[c] = sub.addConstr(quicksum(quicksum(y[i,p,c] for p in serverType) for i in station) <= 1)
    for c in callHighs:
        c_test2[c] = sub.addConstr(quicksum(y[i,'A',c] for i in station) <= 1)
        c_test3[c] = sub.addConstr(quicksum(y[i,'B',c] for i in station) <= 1)


    sub.update()
    sub.modelsense = GRB.MAXIMIZE
    sub.optimize()

    return sub.objVal


def solve(numOverCall, numCall, callHigh, callLow, location, nearStation, busyCall):

    m = Model("Stochastic Ambulance Location with Two Types of Servers")
    #m.params.logtoconsole = 0
    m.modelsense = GRB.MAXIMIZE
    m.setParam('TimeLimit', 7200)

    ### decision variables

    x = {} # deployment
    y = {} # dispatch
    z = {} # cover
    zA = {} # cover, high, by ALS
    zB = {} # cover, high, by BLS + ALS
    g = {} # lost call

    for i in station : 
        for p in serverType : 
            x[i,p] = m.addVar(vtype = GRB.INTEGER, ub = numServer[p])
            #x[i,p] = m.addVar(vtype = GRB.BINARY)
            
    for i in station : 
        for p in serverType : 
            for s in scenario : 
                for c in range(numCall[s]) :
                    if ifRelax:
                        y[i,p,s,c] = m.addVar(ub=1.0, vtype=GRB.CONTINUOUS)
                    else:
                        y[i,p,s,c] = m.addVar(vtype = GRB.BINARY)
                        
    for s in scenario : 
        for c in range(numCall[s]) :
            if ifRelax:
                g[s,c] = m.addVar(obj = -penalty, ub=1.0, vtype = GRB.CONTINUOUS)
            else:
                g[s,c] = m.addVar(obj = -penalty, vtype = GRB.BINARY)
        for c in callHigh[s] :
            if ifRelax:
                z[s,c] = m.addVar(obj = wH, ub=1.0, vtype = GRB.CONTINUOUS)
                zA[s,c] = m.addVar(ub = 1.0, vtype = GRB.CONTINUOUS)      
                zB[s,c] = m.addVar(ub = 1.0, vtype = GRB.CONTINUOUS)
            else:
                z[s,c] = m.addVar(obj = wH, vtype = GRB.BINARY)
                zA[s,c] = m.addVar(vtype = GRB.BINARY)       
                zB[s,c] = m.addVar(vtype = GRB.BINARY)
        for c in callLow[s] : 
            if ifRelax:
                z[s,c] = m.addVar(obj = wL, ub=1.0, vtype = GRB.CONTINUOUS)
            else:
                z[s,c] = m.addVar(obj = wL, vtype = GRB.BINARY)

    m.update()

    ### constraints

    # cannot deploy more than the fleet size.
    c_deploy = {}
    for p in serverType : 
        c_deploy[p] = m.addConstr(quicksum(x[i,p] for i in station) == numServer[p]) # maybe I can make it equality?
        
    # cannot dispatch more than deployed.
    c_dispatch = {}
    for i in station : 
        for p in serverType : 
            for s in scenario : 
                for c in range(numCall[s]) : 
                    c_dispatch[i,p,s,c] = m.addConstr(y[i,p,s,c] + quicksum(y[i,p,s,d] for d in busyCall[s][i,c]) <= x[i,p])

    # low priority calls can be covered by nearby server of any type.
    c_coverLow = {}
    for s in scenario : 
        for c in callLow[s] : 
            c_coverLow[s,c] = m.addConstr(z[s,c] <= quicksum(quicksum(y[i,p,s,c] for i in nearStation[s][c]) for p in serverType))

    # high priority calls can be covered either (1) nearby ALS or by (2) nearby BLS and faraway ALS.
    c_coverHigh1 = {}
    c_coverHigh2A = {}
    c_coverHigh2B = {}
    c_coverHigh = {}
    for s in scenario : 
        for c in callHigh[s] : 
            c_coverHigh1[s,c] = m.addConstr(zA[s,c] <= quicksum(y[i,'A',s,c] for i in nearStation[s][c]))
            c_coverHigh2A[s,c] = m.addConstr(zB[s,c] <= quicksum(y[i,'B',s,c] for i in nearStation[s][c]))
            #c_coverHigh2B[s,c] = m.addConstr(zB[s,c] <= quicksum(y[i,'A',s,c] for i in station))
            # new constraint coverHigh2B that prevents double-counting behavior
            c_coverHigh2B[s,c] = m.addConstr(zB[s,c] <= quicksum(y[i,'A',s,c] for i in (k for k in station if k not in nearStation[s][c])))
            c_coverHigh[s,c] = m.addConstr(z[s,c] <= zA[s,c] + zB[s,c])

    # penalize calls that are lost (no server is dispatched)
    c_loss = {}
    for s in scenario : 
        for c in range(numCall[s]) : 
            c_loss[s,c] = m.addConstr(1-g[s,c] <= quicksum(quicksum(y[i,p,s,c] for i in station) for p in serverType))

    #### TODO set constraints for # of dispatches for test purpose.. see how the answer differs.

    optsol_A, optsol_B = [],[]
    c_test1, c_test2, c_test3 = {}, {}, {}
    for s in scenario:
        for c in callLow[s]:
            c_test1[s,c] = m.addConstr(quicksum(quicksum(y[i,p,s,c] for p in serverType) for i in station) <= 1)
        for c in callHigh[s]:
            c_test2[s,c] = m.addConstr(quicksum(y[i,'A',s,c] for i in station) <= 1)
            c_test3[s,c] = m.addConstr(quicksum(y[i,'B',s,c] for i in station) <= 1)
            
    m.update()        
    m.optimize()
    for i in station :
        if x[i,'A'].x > 0.1 :
            optsol_A.append(i)
        if x[i,'A'].x > 1.1 :
            optsol_A.append(i)
        if x[i,'B'].x > 0.1:
            optsol_B.append(i)
        if x[i,'B'].x > 1.1 :
            optsol_B.append(i)
    opt = {}
    for i in station:
        for p in serverType:
            opt[i,p] = x[i,p].x

    return m.objVal, optsol_A, optsol_B, opt




print 'now solving DEF...'
objDEF, optDEF_A, optDEF_B, opt = solve(numOverCall, numCall, callHigh, callLow, location, nearStation, busyCall)
print 'DEF objVal              :', objDEF/ float(numHighCall*wH + numLowCall*wL)
print "DEF solution            :", "ALS at",optDEF_A, "BLS at",optDEF_B  


endtime = ti.time()
print 'time elapsed        :', endtime - starttime


#sys.exit(0) ##### only for DEF


# reevaluate with IP SSP
objEval_LP, objEval_IP = 0.0, 0.0
for s in scenario:
    v1,v2,v3 = subproblem(opt, numOverCall[s], numCall[s], callHigh[s], callLow[s], location[s], nearStation[s], busyCall[s])
    objEval_LP += v1
    objEval_IP += solveSSP_Int(opt, numOverCall[s], numCall[s], callHigh[s], callLow[s], location[s], nearStation[s], busyCall[s])
print 'coverage reevaluated (LP):', objEval_LP / float(numHighCall*wH + numLowCall*wL)
print 'coverage reevaluated (IP):', objEval_IP / float(numHighCall*wH + numLowCall*wL)

########### Mean value problem is now solving. Check solution and then Fisx to solve Mean Value Solution, and then compare to VSS. 