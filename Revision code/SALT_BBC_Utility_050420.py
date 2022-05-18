########################################
# SALT with BBC solution method for Deterministic Utility
# last update 12/22/18
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

#import sample_Charlotte_Utility_112619 as inputs
#import sample_Hanover_122618 as inputs
import sample_Hanover_Utlity_112519 as inputs
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
#R= inputs.R
Rl = inputs.Rl
Rh = inputs.Rh

##### call generation
callHigh, callLow = {},{}
location, nearStation, busyCall = {},{},{}
arrivalTime, serviceTime = {}, {}
numOverCall, numCall = {}, {}
numCallTotal, numHighCall, numLowCall, numHighCallIn, numLowCallIn = 0,0,0,0,0

for s in scenario :
    numOverCall[s], numCall[s], callHigh[s], callLow[s], location[s], nearStation[s], busyCall[s], arrivalTime[s], serviceTime[s]= inputs.genCall()

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



##### Master Problem
master = Model('SALT Master Problem')
master.params.logtoconsole = 0
master.modelsense = GRB.MAXIMIZE
master.setParam('TimeLimit', 7200)

### master problem variables
x = {} # deployment # first stage only has deployment variable x
for i in station : 
    for p in serverType : 
        x[i,p] = master.addVar(vtype = GRB.CONTINUOUS,ub=2)
        #x[i,p] = master.addVar(vtype = GRB.INTEGER, ub = numServer[p])
        #x[i,p] = master.addVar(vtype = GRB.BINARY)    
theta = {} # subproblem obj
for s in scenario:
    #theta[s] = master.addVar(obj = 1.0, vtype = GRB.CONTINUOUS, ub = numCall[s])
    theta[s] = master.addVar(obj = 1.0, vtype = GRB.CONTINUOUS, ub = wH * len(callHigh[s]) + wL * len(callLow[s]))
master.update()

### master problem constraints
# cannot deploy more than the fleet size.
c_deploy = {}
for p in serverType : 
    c_deploy[p] = master.addConstr(quicksum(x[i,p] for i in station) == numServer[p]) # maybe I can make it equality?

#Cannot assign more abulances than there is station capacity 
c_capacity = {}
for i in station : 
    c_capacity[p] = master.addConstr(quicksum(x[i,p] for p in serverType) <= 2) # maybe I can make it equality?
master.update()




##### Subproblem, linearly relaxed    
def subproblem(opt,numOverCall, numCall, callHigh, callLow, location, nearStation, busyCall):

    sub = Model('SALT Subproblem')
    sub.params.logtoconsole = 0
    sub.modelsense = GRB.MAXIMIZE

    ### subproblem variables
    y = {} # dispatch
    for i in station:
        for p in serverType:
            #for c in range(numCall): OLD
             #   y[i,p,c] = sub.addVar(vtype = GRB.CONTINUOUS) OLD
            for c in callHigh: #new
                y[i,p,c] = sub.addVar(vtype = GRB.CONTINUOUS) #new
        for c in callLow: #need to change weights to include R
            y[i,'A',c] = sub.addVar(obj = wL*ULA*Rl[i,location[c]], vtype = GRB.CONTINUOUS) #new
            y[i,'B',c] = sub.addVar(obj = wL*ULB*Rl[i,location[c]], vtype = GRB.CONTINUOUS) #new
            
    zAB = {} # cover #new
    zA = {} # cover, high, by ALS
    zB = {} # cover, high, by BLS + ALS
    for i in station:
        for c in callHigh: #need to change weights to include R
            zAB[i,c] = sub.addVar(obj = wH*UHA*Rh[i,location[c]], vtype = GRB.CONTINUOUS) #new
            zA[i,c] = sub.addVar(obj = wH*UHA*Rh[i,location[c]],vtype = GRB.CONTINUOUS) #new 
            zB[i,c] = sub.addVar(obj = wH*UHB*Rh[i,location[c]],vtype = GRB.CONTINUOUS) #new 
    #for c in callLow: OLD
    #    z[c] = sub.addVar(obj = wL, vtype = GRB.CONTINUOUS) OLD

    g = {} # lost call
    for c in range(numCall):
        g[c] = sub.addVar(obj = -penalty, vtype = GRB.CONTINUOUS)
    sub.update()

    ### subproblem constraints
    # cannot dispatch more than deployed. SAME
    c_dispatch = {}
    for i in station : 
        for p in serverType : 
            for c in range(numCall) : 
                c_dispatch[i,p,c] = sub.addConstr(y[i,p,c] + quicksum(y[i,p,d] for d in busyCall[i,c]) <= opt[i,p])

    
    c_coverLow = {}
    for c in callLow : #cant send more than one vehicle to a low priority call
    #c_coverLow[c] = sub.addConstr(z[c] - quicksum(quicksum(y[i,p,c] for i in nearStation[c]) for p in serverType) <= 0) OLD
        c_coverLow[c] = sub.addConstr( quicksum(quicksum(y[i,p,c] for i in station) for p in serverType) <= 1) #new constraint 18
    
    # high priority calls can be covered either (1) nearby ALS_NVT or by (2) nearby BLS and faraway ALS_NVT.
    c_coverHigh1 = {}
    c_coverHigh2A = {}
    c_coverHigh2B = {}
    c_coverHigh2C = {} #new
    c_coverHigh2D = {} #new
    c_coverHigh = {}
    for p in serverType:
        for c in callHigh: #can't send more than one vehicle of each type to a high proirty call
            c_coverHigh1[p,c] = sub.addConstr(quicksum(y[i,p,c] for i in station) <= 1) #new constraint 17
    for i in station:
        for c in callHigh:
            c_coverHigh2A[i,c] = sub.addConstr(zA[i,c] - y[i,'A',c] <= 0) #NEW constraint 20
            c_coverHigh2B[i,c] = sub.addConstr(zB[i,c] - y[i,'B',c] <= 0)#NEW constraint 21
            c_coverHigh2C[i,c] = sub.addConstr(zAB[i,c] - quicksum(y[i,'A',c] for i in station) <= 0)#NEW constraint 22
            c_coverHigh2D[i,c] = sub.addConstr(zAB[i,c] - y[i,'B',c] <= 0)#NEW constraint 23
    for c in callHigh:
        c_coverHigh[c] = sub.addConstr(quicksum(zAB[i,c] + zA[i,c] + zB[i,c] for i in station) <= 1) #new contraint 19

    # penalize calls that are lost (no server is dispatched) SAME
    c_loss = {}
    for c in range(numCall) : 
        c_loss[c] = sub.addConstr(0 - g[c] - quicksum(quicksum(y[i,p,c] for i in station) for p in serverType) <= -1)

    # need to add upper bounds for all (originally) binary variables
    c_y = {}
    for i in station:
        for p in serverType:
            for c in range(numCall):
                c_y[i,p,c] = sub.addConstr(y[i,p,c] <= 1)
  #  c_z = {} OLD
   # for c in range(numCall): OLD
    #    c_z[c] = sub.addConstr(z[c] <= 1) OLD

    c_zA, c_zB = {}, {}
    c_zAB = {} #new
    for i in station:
        for c in callHigh:
            c_zA[i,c] = sub.addConstr(zA[i,c] <= 1)
            c_zB[i,c] = sub.addConstr(zB[i,c] <= 1)
            c_zAB[i,c] = sub.addConstr(zAB[i,c] <= 1) #new
    c_g = {}
    for c in range(numCall):
        c_g[c] = sub.addConstr(g[c] <= 1)

    sub.update()

    sub.optimize()

    # this part is for benders cut
    rhs = 0.0
    for c in range(numCall):
            rhs += c_g[c].Pi - c_loss[c].Pi
    for i in station:  
        for c in callHigh:
            rhs += c_zA[i,c].Pi + c_zB[i,c].Pi + c_zAB[i,c].Pi #new
 
    xcoef = {}
    for i in station:
        for p in serverType:
            for c in range(numCall):
                xcoef[i,p,c] = c_dispatch[i,p,c].Pi
                rhs += c_y[i,p,c].Pi

    return sub.objVal, rhs, xcoef


##### cutting plane loop for phase 0: comment out to skip
cutfound = 1  ## keep track if any violated cuts were found  (set cutfound = 0 to skip this loop)
iteration = 1
totcuts = 0
starttime_phase0 = ti.time()
tottime = 0
while cutfound and tottime < 2500:

    print '================ Iteration ', iteration, ' ==================='
    iteration = iteration + 1
    cutfound = 0

    ### 1. solve current master problem
    master.update()
    master.optimize()

    print 'current LP master objval = ', master.objVal

    ### 2. update subproblem by fixing RHS constraints for each scenario and master solution
    opt = {}
    for i in station:
        for p in serverType:
            opt[i,p] = x[i,p].x

    for s in scenario:
        subObjVal, rhs, xcoef = subproblem(opt, numOverCall[s], numCall[s], callHigh[s], callLow[s], location[s], nearStation[s], busyCall[s])
        if theta[s].x > subObjVal + 0.00001: # violation tolerance
            totcuts = totcuts + 1
            # add benders cut
            master.addConstr(theta[s] <=  rhs + quicksum(quicksum(quicksum(xcoef[i,p,c] * x[i,p] for c in range(numCall[s])) for p in serverType) for i in station))
            cutfound = 1
            #print 'cut:', rhs, '+'
            #print s, theta[s].x, subObjVal, numCall[s], len(callHigh[s]), len(callLow[s])
    tottime = ti.time() - starttime_phase0
    
print 'Benders cuts in LP master: ', totcuts
endtime_phase0 = ti.time()


### Now declare first stage variables to be integer (or binary, test both)
for i in station:
    for p in serverType:
        x[i,p].vType = GRB.INTEGER


### Define the callback function that Gurobi will call when it finds an integer feasible solution 
### This is where you need to search for more Benders cuts and add them if any violated

def BendersCallback(model, where):
    if where == GRB.Callback.MIPSOL:
        opt = {}
        for i in station:
            for p in serverType:
                opt[i,p] = model.cbGetSolution(model._x[i,p])
        for s in scenario:
            subObjVal, rhs, xcoef = subproblem(opt,numOverCall[s], numCall[s], callHigh[s], callLow[s], location[s], nearStation[s], busyCall[s])
            if model.cbGetSolution(model._theta[s]) > subObjVal + 0.00001: # violation tolerance
                model.cbLazy(model._theta[s] <=  rhs + quicksum(quicksum(quicksum(xcoef[i,p,c] * model._x[i,p] for c in range(numCall[s])) for p in serverType) for i in station))
                #print 'scenario', s, 'cut added:', model.cbGetSolution(theta[s]), subObjVal, rhs, 'calls:', numCall[s], len(callHigh[s]), len(callLow[s])

            


### Pass BendersCallback as argument to the optimize function on the master
master.params.lazyConstraints = 1
master.params.logtoconsole = 1
master._x = x
master._theta = theta

### also set optimality gap termination criteria as 1 percent
#master.params.MIPGap = 0.01

## also update timelimit to subtract phase 0 time from 3600s
phase0time = endtime_phase0 - starttime_phase0
master.setParam('TimeLimit', 7200 - phase0time)

master.optimize(BendersCallback)
#print master.objVal


### Display solution
optsol_A, optsol_B = [],[]
for i in station :
    if x[i,'A'].x > 0.5 :
        optsol_A.append(i)
        if x[i,'A'].x > 1.5:
            optsol_A.append(i)
    if x[i,'B'].x > 0.5:
        optsol_B.append(i)
        if x[i,'B'].x > 1.5:
            optsol_B.append(i)
       
print "solution            :", "ALS at",optsol_A, "BLS at",optsol_B           
print "coverage            :", master.objVal / float(numHighCall*wH + numLowCall*wL)
#print "subproblem obj:"
#for s in scenario:
#    print s, theta[s].x

endtime = ti.time()
print 'time elapsed        :', endtime - starttime







##### Double check: reevaluate the optimal solution

### Solve second-stage problem to reevaluate solutions from linear relaxed problem

def solveSSP_Int(opt, numOverCall, numCall, callHighs, callLows, locations, nearStations, busyCalls) : 

    sub = Model("Subproblem")
    sub.modelsense = GRB.MAXIMIZE
    #sub.params.logtoconsole = 0
    sub.params.outputflag = 0

    ### subproblem variables

    y = {} # dispatch
    for i in station:
        #for p in serverType: OLD
            #for c in range(numCall): OLD
             #   y[i,p,c] = sub.addVar(vtype = GRB.CONTINUOUS) OLD
        for p in serverType: #new
            for c in callHighs: #new
                y[i,p,c] = sub.addVar(vtype = GRB.CONTINUOUS) #new
        for c in callLows: #need to change weights to include R
            y[i,'A',c] = sub.addVar(obj = wL*ULA*Rl[i,locations[c]], vtype = GRB.CONTINUOUS) #new
            y[i,'B',c] = sub.addVar(obj = wL*ULB*Rl[i,locations[c]], vtype = GRB.CONTINUOUS) #new
            
    zAB = {} # cover #new
    zA = {} # cover, high, by ALS
    zB = {} # cover, high, by BLS + ALS
    for i in station:
        for c in callHighs: #need to change weights to include R
            zAB[i,c] = sub.addVar(obj = wH*UHA*Rh[i,locations[c]], vtype = GRB.CONTINUOUS) #new
            zA[i,c] = sub.addVar(obj = wH*UHA*Rh[i,locations[c]],vtype = GRB.CONTINUOUS) #new 
            zB[i,c] = sub.addVar(obj = wH*UHB*Rh[i,locations[c]],vtype = GRB.CONTINUOUS) #new 
    #for c in callLow: OLD
    #    z[c] = sub.addVar(obj = wL, vtype = GRB.CONTINUOUS) OLD

    g = {} # lost call
    for c in range(numCall):
        g[c] = sub.addVar(obj = -penalty, vtype = GRB.CONTINUOUS)
    sub.update()

    ### subproblem constraints
    # cannot dispatch more than deployed. SAME
    c_dispatch = {}
    for i in station : 
        for p in serverType : 
            for c in range(numCall) : 
                c_dispatch[i,p,c] = sub.addConstr(y[i,p,c] + quicksum(y[i,p,d] for d in busyCalls[i,c]) <= opt[i,p])

    # low priority calls can be covered by nearby server of any type. NOW cant send more than one vehicle to low priority
    c_coverLow = {}
    for c in callLows :  
    #c_coverLow[c] = sub.addConstr(z[c] - quicksum(quicksum(y[i,p,c] for i in nearStation[c]) for p in serverType) <= 0) OLD
        c_coverLow[c] = sub.addConstr( quicksum(quicksum(y[i,p,c] for i in station) for p in serverType) <= 1) #new constraint 18
    # high priority calls can be covered either (1) nearby ALS_NVT or by (2) nearby BLS and faraway ALS_NVT.
    c_coverHigh1 = {}
    c_coverHigh2A = {}
    c_coverHigh2B = {}
    c_coverHigh2C = {} #new
    c_coverHigh2D = {} #new
    c_coverHigh = {}
    for p in serverType:
        for c in callHighs : 
            c_coverHigh1[p,c] = sub.addConstr(quicksum(y[i,p,c] for i in station) <= 1) #new constraint 17
    for i in station:
        for c in callHighs:
            c_coverHigh2A[i,c] = sub.addConstr(zA[i,c] - y[i,'A',c] <= 0) #NEW constraint 20
            c_coverHigh2B[i,c] = sub.addConstr(zB[i,c] - y[i,'B',c] <= 0)#NEW constraint 21
            c_coverHigh2C[i,c] = sub.addConstr(zAB[i,c] - quicksum(y[i,'A',c] for i in station) <= 0)#NEW constraint 22
            c_coverHigh2D[i,c] = sub.addConstr(zAB[i,c] - y[i,'B',c] <= 0)#NEW constraint 23
    for c in callHighs:
        c_coverHigh[c] = sub.addConstr(quicksum(zAB[i,c] + zA[i,c] + zB[i,c] for i in station) <= 1) #new contraint 19

    # penalize calls that are lost (no server is dispatched) SAME
    c_loss = {}
    for c in range(numCall) : 
        c_loss[c] = sub.addConstr(0 - g[c] - quicksum(quicksum(y[i,p,c] for i in station) for p in serverType) <= -1)
    '''
    #### TODO set constraints for # of dispatches for test purpose.. see how the answer differs.
    c_test1, c_test2, c_test3 = {}, {}, {}
    for c in callLows:
        c_test1[c] = sub.addConstr(quicksum(quicksum(y[i,p,c] for p in serverType) for i in station) <= 1)
    for c in callHighs:
        c_test2[c] = sub.addConstr(quicksum(y[i,'A',c] for i in station) <= 1)
        c_test3[c] = sub.addConstr(quicksum(y[i,'B',c] for i in station) <= 1)'''


    sub.update()
    sub.modelsense = GRB.MAXIMIZE
    sub.optimize()

    return sub.objVal


objEval_LP, objEval_IP = 0.0, 0.0
opt = {}
for i in station:
    for p in serverType:
        opt[i,p] = x[i,p].x
for s in scenario:
    v1,v2,v3 = subproblem(opt, numOverCall[s], numCall[s], callHigh[s], callLow[s], location[s], nearStation[s], busyCall[s])
    objEval_LP += v1
    objEval_IP += solveSSP_Int(opt, numOverCall[s], numCall[s], callHigh[s], callLow[s], location[s], nearStation[s], busyCall[s])
print 'coverage reevaluated (LP):', objEval_LP / float(numHighCall*wH + numLowCall*wL)
print 'coverage reevaluated (IP):', objEval_IP / float(numHighCall*wH + numLowCall*wL)

print 'number of servers:', numServer







#################################################################################################################
