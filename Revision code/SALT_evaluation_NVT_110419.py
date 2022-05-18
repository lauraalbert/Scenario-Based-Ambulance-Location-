########################################
# SALT - for evaluating solutions for NVT extenstion
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

#import sample_Charlotte_112518 as inputs #soovins
#import sample_Charlotte_NVT_093019 as inputs #mine
import sample_Hanover_NTV_042720 as inputs

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

f = "12pNTV_Coverage_Hannover_BLS" + str(numServer["B"]) + ".txt"
sys.stdout = open(str(f),'w')
##### call generation
callHigh, callLow = {},{}
location, nearStation, busyCall = {},{},{}
arrivalTime, serviceTime = {}, {}
numOverCall, numCall = {}, {}
nearStationNTV = {}

numCallTotal, numHighCall, numLowCall, numHighCallIn, numLowCallIn = 0,0,0,0,0
for s in scenario :
    numOverCall[s], numCall[s], callHigh[s], callLow[s], location[s], nearStation[s], busyCall[s], arrivalTime[s], serviceTime[s] ,  nearStationNTV[s]= inputs.genCall()

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

def solveSSP_Int(opt, numOverCall, numCall, callHighs, callLows, locations, nearStations, busyCalls, nearStationsNTV) : 

    sub = Model("Subproblem")
    sub.modelsense = GRB.MAXIMIZE
    #sub.params.logtoconsole = 0
    sub.params.outputflag = 0

    ### subproblem variables
    y = {} # dispatch
    for i in station:
        for p in serverType:
            for c in range(numCall):
                y[i,p,c] = sub.addVar(vtype = GRB.BINARY)
    z = {} # cover
    #A# zA = {} # cover, high, by ALS
    #B #zB = {} # cover, high, by BLS + ALS
    for c in callHighs:
        z[c] = sub.addVar(obj = wH, vtype = GRB.BINARY)
        #C# zA[c] = sub.addVar(vtype = GRB.CONTINUOUS)
        #D# zB[c] = sub.addVar(vtype = GRB.CONTINUOUS)
    for c in callLows:
        z[c] = sub.addVar(obj = wL, vtype = GRB.BINARY)
        
    g = {} # lost call
    for c in range(numCall):
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
        #E# c_coverLow[c] = sub.addConstr(z[c] - quicksum(quicksum(y[i,p,c] for i in nearStation[c]) for p in serverType) <= 0)
        c_coverLow[c] = sub.addConstr(z[c] - quicksum(y[i,'B',c] for i in nearStations[c]) <= 0)

    # high priority calls can be covered either (1) nearby ALS or by (2) nearby BLS and faraway ALS.
    c_coverHigh1 = {}
    c_coverHigh2A = {}
    c_coverHigh2B = {}
    c_coverHigh = {}
    for c in callHighs : 
        #F# c_coverHigh1[c] = sub.addConstr(zA[c] - quicksum(y[i,'A',c] for i in nearStation[c]) <= 0)
        #c_coverHigh1[c] = sub.addConstr(z[c] - quicksum(y[i,'A',c] for i in nearStations[c]) <= 0) #Change for al i later
        #Fnew#
        c_coverHigh1[c] = sub.addConstr(z[c] - quicksum(y[i,'A',c] for i in nearStationsNTV[c]) <= 0) #Change for al i later
        #G# c_coverHigh2A[c] = sub.addConstr(zB[c] - quicksum(y[i,'B',c] for i in nearStation[c]) <= 0)
        c_coverHigh2A[c] = sub.addConstr(z[c] - quicksum(y[i,'B',c] for i in station) <= 0)
        #c_coverHigh2B[c] = sub.addConstr(zB[c] - quicksum(y[i,'A',c] for i in station) <= 0)
        # new constraint coverHigh2B that prevents double-counting behavior
        #H# c_coverHigh2B[c] = sub.addConstr(zB[c] - quicksum(y[i,'A',c] for i in (k for k in station if k not in nearStation[c])) <= 0)
        #I# c_coverHigh[c] = sub.addConstr(z[c] - zA[c] - zB[c] <= 0)

    # penalize calls that are lost (no server is dispatched)
    c_loss = {}
    for c in range(numCall) : 
        #J# c_loss[c] = sub.addConstr(0 - g[c] - quicksum(quicksum(y[i,p,c] for i in station) for p in serverType) <= -1)
        c_loss[c] = sub.addConstr(0 - g[c] - quicksum(y[i,'B',c] for i in station) <= -1)

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
    ''' 
    for c in range(numCall) : 
        if g[c].x > .5:
            print "call ", c, " lost"
            for i in station:            
                for p in serverType: 
                    if y[i,p,c].x > 0.9:
                        print "station ", i , "vehicle ", p, " call ", c, " value ", y[i,p,c].x
                        '''
    # Let's count actions
    #A# remove coveredByALS since it is not just "covered" (by both)
    #coveredByALS, coveredByBoth, lost = 0, 0, 0
    coveredByBoth, lost = 0, 0
    lowCovered, lowLost = 0,0
    for c in callHighs:
        #A# 
        if z[c].x > 0.5:
            coveredByBoth += 1
        #if zA[c].x > 0.5:
          #  coveredByALS += 1
        #elif zB[c].x > 0.5:
            #coveredByBoth += 1
        elif g[c].x > 0.5:
            lost += 1
    for c in callLows:
        if z[c].x > 0.5:
            lowCovered += 1
        elif g[c].x > 0.5:
            lowLost += 1
            
    
    #A# return sub.objVal, coveredByALS, coveredByBoth, lost, lowCovered, lowLost
    return sub.objVal,  coveredByBoth, lost, lowCovered, lowLost

##Charlotte Locations###
### sensitivity analysis for 24 people
#ALSStations, BLSStations = [], [29, 44, 57, 52, 80, 62, 88, 41, 72, 91, 75, 83]
#ALSStations, BLSStations = [52, 72], [29, 44, 57, 52, 80, 62, 88, 41, 72, 91, 83]
#ALSStations, BLSStations = [52, 80, 41, 72], [29, 44, 57, 52, 80, 62, 41, 72, 91, 83]
#ALSStations, BLSStations = [44, 96, 80, 62, 41, 83], [44, 57, 52, 80, 62, 41, 72, 91, 83]
#ALSStations, BLSStations = [44, 57, 52, 84, 16, 88, 72, 100], [44, 57, 52, 80, 62, 41, 72, 83]
#ALSStations, BLSStations = [29, 44, 57, 63, 5, 88, 41, 72, 83, 100], [44, 57, 52, 80, 62, 41, 72]
#ALSStations, BLSStations = [29,44,9,57,6,104,80,62,88,41,75,83], [44, 52, 80,62,41,72]

### sensitivity analysis for 30 people
#ALSStations, BLSStations =  [],[35, 29, 44, 57, 5, 52, 96, 80, 62, 88, 41, 72, 91, 75, 83]
#ALSStations, BLSStations =  [52, 72], [35, 29, 44, 57, 5, 52, 80, 62, 88, 41, 72, 91, 75, 83]
#ALSStations, BLSStations = [52, 80, 41, 72], [29, 44, 57, 5, 52, 80, 62, 88, 41, 72, 91, 75, 83]
#ALSStations, BLSStations = [44, 96, 80, 62, 41, 83] , [29, 44, 57, 75, 52, 80, 62, 88, 41, 72, 91, 83] #new 75 for 63
#ALSStations, BLSStations = [44, 15, 57, 52, 84, 88, 72, 100], [29, 44, 57, 52, 80, 62, 88, 41, 72, 91, 83]
#ALSStations, BLSStations = [29, 44, 57, 5, 84, 80, 62, 88, 41, 100],[29, 44, 57, 52, 80, 62, 41, 72, 91, 83]
#ALSStations, BLSStations = [29, 44, 9, 57, 6, 80, 62, 88, 41, 75, 83, 100],[44, 57, 52, 80, 62, 41, 72, 91, 83]
#ALSStations, BLSStations = [29, 95, 44, 9, 57, 63, 6, 96, 80, 102, 41, 72, 75, 100],[44, 57, 52, 80, 62, 41, 72, 83]
#ALSStations, BLSStations = [29, 95, 44, 9, 57, 63, 6, 52, 96, 80, 102, 41, 72, 75, 100, 18], [44, 57, 52, 80, 41, 72, 83]
#ALSStations, BLSStations = [29, 95, 44, 9, 57, 57, 63, 6, 96, 16, 62, 102, 88, 41, 72, 75, 100, 18], [44, 52, 80, 62, 41, 72]

### sensitivity analysis for 36 people
#ALSStations, BLSStations =  [],	[35, 29, 44, 57, 5, 52, 80, 62, 102, 88, 41, 41, 72, 72, 91, 75, 83, 100]
#ALSStations, BLSStations = [52, 72], 	[29, 44, 57, 5, 52, 52, 96, 80, 62, 102, 88, 41, 41, 72, 91, 75, 83]
#ALSStations, BLSStations = [52, 80, 41, 72], 	[35, 29, 44, 57, 5, 52, 96, 80, 62, 88, 41, 41, 72, 91, 75, 83]
#ALSStations, BLSStations = [44, 96, 80, 62, 41, 83],	[35, 29, 44, 57, 5, 52, 96, 80, 62, 88, 41, 72, 91, 75, 83]
#ALSStations, BLSStations = [44, 57, 52, 84, 16, 88, 72, 100],	[35, 29, 44, 57, 5, 52, 80, 62, 88, 41, 72, 91, 75, 83]
#ALSStations, BLSStations = [29, 44, 57, 5, 84, 80, 62, 88, 41, 100],	[29, 44, 57, 5, 52, 80, 62, 88, 41, 72, 91, 75, 83]
#ALSStations, BLSStations = [29, 44, 9, 57, 6, 80, 62, 88, 41, 75, 83, 100],	[29, 44, 57, 52, 80, 62, 88, 41, 72, 91, 75, 83]
#ALSStations, BLSStations = [29, 95, 44, 15, 57, 63, 6, 84, 96, 104, 80, 41, 72, 75], 	[29, 44, 57, 52, 80, 62, 41, 72, 91, 75, 83]
#ALSStations, BLSStations = [29, 95, 44, 9, 57, 63, 6, 96, 80, 62, 102, 41, 41, 72, 75, 100],	[29, 44, 57, 52, 80, 62, 41, 72, 91, 83]
#ALSStations, BLSStations = [29, 95, 44, 9, 57, 57, 63, 6, 96, 16, 80, 62, 102, 41, 72, 75, 100, 18], 	[44, 57, 52, 80, 62, 41, 72, 91, 83]
#ALSStations, BLSStations = [29, 31, 95, 44, 9, 57, 63, 6, 52, 84, 96, 16, 104, 80, 62, 102, 88, 41, 41, 75],	[44, 57, 52, 80, 62, 41, 72, 83]
#ALSStations, BLSStations = [29, 29, 95, 44, 44, 57, 57, 63, 63, 6, 5, 5, 104, 104, 80, 102, 88, 41, 72, 75, 83, 18] ,	[44, 57, 52, 80, 41, 72, 83]
#CHECK ALSStations, BLSStations = [29, 95, 44, 9, 57, 63, 7, 5, 96, 96, 16, 62, 102, 102, 88, 41, 41, 72, 72, 75, 100, 18],[44, 52, 80, 62, 41, 72]

#Hannover Locations###
###Sensitivity analysis for 12 people
#ALSStations, BLSStations =  [],	[1,4,7,13,14,16]
#ALSStations, BLSStations = [1,6],[6, 7, 10, 14, 16]
#ALSStations, BLSStations = [1,6,7,11], 	[7,13,14,16]
#ALSStations, BLSStations = [1,6,10,11,14,15],	[6,7,16]
#ALSStations, BLSStations = [1,4,6,10,11,12,14,15],	[1,7]
    

###Sensitivity analysis for 16 people
#ALSStations, BLSStations = [],	[1, 4, 7, 11, 12, 13, 14, 16]
#ALSStations, BLSStations =[1, 6],	[1, 4, 7, 12, 13, 14, 16]
#ALSStations, BLSStations =[6, 10, 14, 16], [1, 4, 7, 13, 14, 16]
#ALSStations, BLSStations =[1, 6, 10, 11, 14, 15],	[6, 7, 10, 14, 16]
#ALSStations, BLSStations =[1, 4, 6, 10, 11, 12, 14, 15],	[7, 13, 14, 16]
#ALSStations, BLSStations =[1, 4, 6, 9, 11, 12, 13, 14, 15, 16],	 [6, 7, 16]
#ALSStations, BLSStations =[1, 2, 3, 4, 5, 6, 7, 9, 10, 11, 12, 15], [1, 7]

###Sensitivity analysis for 20 people
#ALSStations, BLSStations = [1, 2, 3, 4, 5, 5, 6, 6, 9, 10, 11, 12, 14, 14, 15, 16],	[1, 7]
#ALSStations, BLSStations = [1, 1, 2, 3, 4, 5, 6, 7, 9, 10, 11, 12, 14, 15],	[6, 7, 16]
#ALSStations, BLSStations = [1, 2, 3, 4, 5, 6, 6, 7, 11, 12, 15, 16], 	[7, 13, 14, 16]
#ALSStations, BLSStations = [1, 2, 4, 6, 6, 11, 12, 14, 15, 16],	[1, 7, 13, 14, 16]
#ALSStations, BLSStations = [1, 6, 6, 11, 12, 14, 15, 16],	[1, 4, 7, 13, 14, 16]
#ALSStations, BLSStations = [1, 6, 10, 11, 14, 15],	[1, 4, 7, 12, 13, 14, 16]
#ALSStations, BLSStations = [6, 10, 14, 16],	[1, 4, 7, 11, 12, 13, 14, 16]
#ALSStations, BLSStations = [1, 6],	[1, 4, 7, 8, 11, 12, 13, 14, 16]
ALSStations, BLSStations = [],	[1, 4, 6, 7, 8, 10, 11, 12, 14, 16]


# set optimal deployment solution
opt = {}
for i in station:
    for p in serverType:
        opt[i,p] = 0
        #print (i, p)
for i in ALSStations:
    opt[i,'A'] += 1
for i in BLSStations:
    opt[i,'B'] += 1

#A# coveredByALSs, coveredByBoths, losts = 0, 0, 0
coveredByBoths, losts = 0, 0
lowCovereds, lowLosts = 0, 0
for s in scenario:
    #print s,
    #A# subObjVal, coveredByALS, coveredByBoth, lost, lowCovered, lowLost = solveSSP_Int(opt, numOverCall[s], numCall[s], callHigh[s], callLow[s], location[s], nearStation[s], busyCall[s],nearStationNTV[s])
    subObjVal, coveredByBoth, lost, lowCovered, lowLost = solveSSP_Int(opt, numOverCall[s], numCall[s], callHigh[s], callLow[s], location[s], nearStation[s], busyCall[s],nearStationNTV[s])
    #A# coveredByALSs += coveredByALS
    coveredByBoths += coveredByBoth
    losts += lost
    lowCovereds += lowCovered
    lowLosts += lowLost

print '\nAction summary:'
#number high calls, num covered by ALS, num covered by BOTH, num lost, num served but not covered
#A# print 'High:', numHighCall,  coveredByBoths, losts, numHighCall - coveredByALSs - coveredByBoths - losts
print 'High:', numHighCall, coveredByBoths, losts, numHighCall - coveredByBoths - losts
print 'Low:', numLowCall, lowCovereds, lowLosts, numLowCall - lowCovereds - lowLosts
endtime = ti.time()
print 'time elapsed        :', endtime - starttime




