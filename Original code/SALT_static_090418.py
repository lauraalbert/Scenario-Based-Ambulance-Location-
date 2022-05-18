########################################################################
# Solve MCLP2
# updated: 09/04/2018
########################################################################

import sys
import csv
from gurobipy import *
import math
import random

# (1) a path to external libraries (numpy, simpy...)
sys.path.append("C:\Python27\Lib\site-packages")
# (2) a path to all other libraries (ctypes, unittest..)
sys.path.append("C:\Python27\Lib")

import sample_Hanover_120418 as input



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


##### generate demand


##### read other inputs
def read_input_for_MCLPP2():

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
    demand_high, demand_low = {}, {} # no need to normalize, since I am just solving covering model!
    for j in customer:
        demand_high[j], demand_low[j] = 0, 0 # 1, 1# 0.0, 0.0
    for l in callLog:
        location = int(l[2])
        if l[1] == '1':
            demand_high[location] += 1
        else:
            demand_low[location] += 1
        

    return dist, response, demand_high, demand_low

def solve_MCLPP2(s_A, s_B, dist_threshold_short, dist_threshold_long):
    
    dist,response, demand_high, demand_low = read_input_for_MCLPP2()
    near_short, near_long = {}, {}
    for j in customer:
        near_short[j], near_long[j] = [], []
        for i in station:
            if dist[i,j] < dist_threshold_short:
                near_short[j].append(i)
            if dist[i,j] < dist_threshold_long:
                near_long[j].append(i)
    
    ## model
    m = Model('Maximal Covering Location Problem for Prioritized Calls and Two Types of Servers')
    m.modelSense = GRB.MAXIMIZE
    m.params.logtoconsole = 0
    
    ## variables
    x = {}              # = 1 if a type q server is located at station i
    for i in station:
        for q in serverType:
            x[i,q] = m.addVar(vtype = GRB.BINARY)        
    h = {}              # = 1 if customer j is covered
    h1, h2 = {}, {}     # hk[j] = 1 if customer j is covered by option k
    l = {}
    for j in customer:
        h[j] = m.addVar(obj = wH*demand_high[j], vtype = GRB.BINARY)
        h1[j] = m.addVar(vtype = GRB.BINARY)    
        h2[j] = m.addVar(vtype = GRB.BINARY)
        l[j] = m.addVar(obj = wL*demand_low[j], vtype = GRB.BINARY)
    m.update()

    ## constraints
    c_server = {}
    c_server['A'] = m.addConstr(quicksum(x[i,'A'] for i in station) <= s_A)   
    c_server['B'] = m.addConstr(quicksum(x[i,'B'] for i in station) <= s_B)   
    c_cover, c_cover1, c_coverA2, c_coverB2, c_coverlow = {}, {}, {}, {}, {}
    for j in customer:
        c_cover1[j] = m.addConstr(h1[j] <= quicksum(x[i,'A'] for i in near_short[j]))
        c_coverB2[j] = m.addConstr(h2[j] <= quicksum(x[i,'B'] for i in near_short[j]))
        c_coverA2[j] = m.addConstr(h2[j] <= quicksum(x[i,'A'] for i in near_long[j]))
        c_cover[j] = m.addConstr(h[j] <= h1[j] + h2[j])
        c_coverlow[j] = m.addConstr(l[j] <= quicksum(quicksum(x[i,q] for q in serverType) for i in near_short[j]))
    m.update() 
        
    m.optimize()

    for i in station:
        for q in serverType:
            if x[i,q].x > 0.5:
                print i, q, x[i,q].x
    
    return m.objVal / (sum(demand_high.values()) + sum(demand_low.values()))

def solve_MCLP(s, dist_threshold):
    dist,response, demand_high, demand_low = read_input_for_MCLPP2()
    near = {}
    demand = {}
    for j in customer:
        near[j] = []
        demand[j] = demand_high[j] + demand_low[j]
        for i in station:
            if dist[i,j] < dist_threshold:
                near[j].append(i)
    
    ## model
    m = Model('Maximal Covering Location Problem')
    m.modelSense = GRB.MAXIMIZE
    m.params.logtoconsole = 0
    
    ## variables
    x = {}              # = 1 if a type q server is located at station i
    for i in station:
        x[i] = m.addVar(vtype = GRB.BINARY)
    y = {}
    for j in customer:
        y[j] = m.addVar(obj = demand[j], vtype = GRB.BINARY)
    m.update()

    ## constraints
    c_cover = {}
    for j in customer:
        c_cover[j] = m.addConstr(y[j] <= quicksum(x[i] for i in near[j]))
    c_server = m.addConstr(quicksum(x[i] for i in station) <= s)
    m.update() 
        
    m.optimize()

    for i in station:
        if x[i].x > 0.5:
            print i, x[i].x

    
    return m.objVal / sum(demand.values())

print len(customer), len(station)
distance, response, demand_high, demand_low = read_input_for_MCLPP2()
for j in customer:
    print "%d %d %d" %(j, demand_high[j], demand_low[j])
obj = solve_MCLPP2(numServer['A'], numServer['B'], distThreshold, 10000)
obj2 = solve_MCLP(numServer['A'] + numServer['B'], distThreshold)

print obj, obj2
