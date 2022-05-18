########################################
# Simulation for SALT -- Dispatcher
# last update 09/06/18
########################################


##### library
import time as ti
import sys
import csv
from gurobipy import *
import random
#import sample_Hanover_122618 as inputs
import sample_Charlotte_112518 as inputs


# we need this
dist = inputs.dist
distThreshold = inputs.distThreshold

# send 'one' closest idle vehicle regardless of the type
def sendTheClosest(ambulances, currentCall):
    serversToSend = []
    isCovered = False

    bestServer = False
    score = 10000
    for amb in ambulances['A']:
        if amb.isBusy == False and dist[amb.station,currentCall.location] < score:
            bestServer = amb
            score = dist[amb.station,currentCall.location]
    for amb in ambulances['B']:
        if amb.isBusy == False and dist[amb.station,currentCall.location] < score:
            bestServer = amb
            score = dist[amb.station,currentCall.location]
    if bestServer:
        serversToSend.append(bestServer)
        isCovered = True if score < distThreshold else False
    return serversToSend, isCovered 

# send the closest idle vehicle that type matches
def sendTheClosestMatching(ambulances, currentCall):
    serversToSend = []
    isCovered = False

    # high priority calls: four options are prioritized
    if currentCall.priority == 'H':

        # (1) check for 'nearby' ALS first
        bestServer = False
        score = 10000
        for amb in ambulances['A']:
            if amb.isBusy == False and dist[amb.station, currentCall.location] < min(distThreshold, score):                
                bestServer = amb
                score = dist[amb.station, currentCall.location]

        if bestServer:
            serversToSend.append(bestServer)
            return serversToSend, True
        
        # (2)  check for ALS + 'nearby' BLS
        # first find closest BLS
        bestServerBLS = False
        scoreBLS = 10000
        for amb in ambulances['B']:
            if amb.isBusy == False and dist[amb.station, currentCall.location] < min(distThreshold, scoreBLS):                
                bestServerBLS = amb
                scoreBLS = dist[amb.station, currentCall.location]
        # and then find the closest ALS
        bestServerALS = False
        scoreALS = 10000
        for amb in ambulances['A']:
            if amb.isBusy == False and dist[amb.station, currentCall.location] < scoreALS:                
                bestServerALS = amb
                scoreALS = dist[amb.station, currentCall.location]
        if bestServerBLS and bestServerALS:
            serversToSend.append(bestServerBLS)
            serversToSend.append(bestServerALS)
            return serversToSend, True

        # (3) check for any closest ALS server
        bestServer = False
        score = 10000
        for amb in ambulances['A']:
            if amb.isBusy == False and dist[amb.station, currentCall.location] < score:                
                bestServer = amb
                score = dist[amb.station, currentCall.location]

        if bestServer:
            serversToSend.append(bestServer)
            return serversToSend, False

        # (4) check for any closest BLS server
        bestServer = False
        score = 10000
        for amb in ambulances['B']:
            if amb.isBusy == False and dist[amb.station, currentCall.location] < score:                
                bestServer = amb
                score = dist[amb.station, currentCall.location]

        if bestServer:
            serversToSend.append(bestServer)
            return serversToSend, False

    # low priority calls: just send the closest idle.        
    elif currentCall.priority == 'L':
        serversToSend, isCovered = sendTheClosest(ambulances, currentCall)

    return serversToSend, isCovered

        
# send the vehicle(s) that yields highest reward
def sendTheHighestReward():
    pass
