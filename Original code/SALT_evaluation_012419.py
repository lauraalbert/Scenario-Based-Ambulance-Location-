########################################
# SALT - for evaluating solutions
# last update 01/24/19
########################################

##### library
import time as ti
import sys
import csv
from gurobipy import *
#sys.path.append("/usr/lib/python2.7/dist-packages")
#sys.path.append("/usr/lib/python2.7/")
#sys.path.append("/usr/lib/pymodules/python2.7/")

# if I call gurobi, somehow other paths are ignored, so manually add them
# (1) a path to external libraries (numpy, simpy...)
sys.path.append('C:\Python27\Lib\site-packages')
# (2) a path to all other libraries (ctypes, unittest..)
sys.path.append('C:\Python27\Lib')
import numpy

#import math
import random

import sample_Charlotte_112518 as inputs

starttime = ti.time()


##### parameters hardcoded
numServer = {'A':inputs.numALS, 'B':inputs.numBLS}
numScenario = inputs.numScenario
scenario = range(1,numScenario + 1)
customer = inputs.customer
numStation = inputs.numStation
station = inputs.station
wH = inputs.wH
wL = inputs.wL
penalty = inputs.penalty
serverType = ['A', 'B']
UHA, UHB, ULA, ULB = inputs.UHA, inputs.UHB, inputs.ULA, inputs.ULB
respProbHigh, respProbLow = inputs.respProbHigh, inputs.respProbLow
ifRelax = inputs.ifRelax


##### call generation
callHigh, callLow = {},{}
location, nearStation, busyCall = {},{},{}
arrivalTime, serviceTime = {}, {}
numOverCall, numCall = {}, {}


numCallTotal, numHighCall, numLowCall, numHighCallIn, numLowCallIn = 0,0,0,0,0
for s in scenario :
    numOverCall[s], numCall[s], callHigh[s], callLow[s], location[s], nearStation[s], busyCall[s], arrivalTime[s], serviceTime[s] = inputs.genCall()

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



### Solve second-stage problem to reevaluate solutions from linear relaxed problem
### and also count the frequency of each dispatch option

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


    # Let's count actions
    coveredByALS, coveredByBoth, lost = 0, 0, 0
    lowCovered, lowLost = 0,0
    for c in callHighs:
        if zA[c].x > 0.5:
            coveredByALS += 1
        elif zB[c].x > 0.5:
            coveredByBoth += 1
        elif g[c].x > 0.5:
            lost += 1
    for c in callLows:
        if z[c].x > 0.5:
            lowCovered += 1
        elif g[c].x > 0.5:
            lowLost += 1
            
    

    return sub.objVal, coveredByALS, coveredByBoth, lost, lowCovered, lowLost


### sensitivity analysis
#ALSStations, BLSStations = [62, 4, 80], [72, 56, 42, 93, 27, 73, 70, 46, 96]
#ALSStations, BLSStations = [62, 58, 27, 79], [99, 72, 58, 42, 41, 73, 46, 96]
#ALSStations, BLSStations = [62, 42, 93, 73, 79], [16, 72, 42, 41, 70, 46, 96]
#ALSStations, BLSStations = [42, 41, 93, 73, 70, 78], [72, 72, 62, 27, 46, 96]
#ALSStations, BLSStations = [62, 58, 42, 41, 46, 96, 80], [72, 93, 27, 73, 70]
#ALSStations, BLSStations = [42, 93, 27, 73, 70, 79, 46, 96], [72, 62, 41, 103]
ALSStations, BLSStations = [16, 42, 42, 93, 73, 73, 70, 70, 46], [72, 79, 96]

# set optimal deployment solution
opt = {}
for i in station:
    for p in serverType:
        opt[i,p] = 0
for i in ALSStations:
    opt[i,'A'] += 1
for i in BLSStations:
    opt[i,'B'] += 1

coveredByALSs, coveredByBoths, losts = 0, 0, 0
lowCovereds, lowLosts = 0, 0
for s in scenario:
    print s,
    subObjVal, coveredByALS, coveredByBoth, lost, lowCovered, lowLost = solveSSP_Int(opt, numOverCall[s], numCall[s], callHigh[s], callLow[s], location[s], nearStation[s], busyCall[s])
    coveredByALSs += coveredByALS
    coveredByBoths += coveredByBoth
    losts += lost
    lowCovereds += lowCovered
    lowLosts += lowLost

print '\nAction summary:'
print 'High:', numHighCall, coveredByALSs, coveredByBoths, losts, numHighCall - coveredByALSs - coveredByBoths - losts
print 'Low:', numLowCall, lowCovereds, lowLosts, numLowCall - lowCovereds - lowLosts
endtime = ti.time()
print 'time elapsed        :', endtime - starttime




