########################################
# SALT
# SALT with stochastic response times and matching utility 
# Branch and Bound, linear SSP
# last update 12/19/18
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
    c_test1, c_test2, c_test3 = {}, {}, {}
    for s in scenario:
        for c in callLow[s]:
            c_test1[s,c] = m.addConstr(quicksum(quicksum(y[i,p,s,c] for p in serverType) for i in station) <= 1)
        for c in callHigh[s]:
            c_test2[s,c] = m.addConstr(quicksum(y[i,'A',s,c] for i in station) <= 1)
            c_test3[s,c] = m.addConstr(quicksum(y[i,'B',s,c] for i in station) <= 1)
            
    m.update()        
    m.optimize()

    optsol_A, optsol_B = [],[]
    for i in station :
        if x[i,'A'].x > 0.1 :
            optsol_A.append(i)
        if x[i,'B'].x > 0.1:
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




#sys.exit(0)






#################################################################################################################
