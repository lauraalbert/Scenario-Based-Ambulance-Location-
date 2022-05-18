The VSS params were used to create a synthetic call bundle that changed via ransdom seed. Since, call locations were randomly generated based on the CDF of call locations of the dataset.

The mean value probelm (MVP) was then solved using the syntheic call bundle using VSS.py

The MVP solution was then re-evaluated by setting the X variables (ambulance locations) in SALT_DEFL_012419.py equal to the solution of the mean value problem.  (i.e SALT_DEFL_012419_ReEvaluatedMV.py)

The stochastic problem was also solved using SALT_DEFL_012419.py, but removed the restictions on the X variables (i.e SALT_DEFL_VSS_061420.py)

The stochastic simulation was solved using Simulation_General.py

SALT_BBC_NTV_03020.py is the updated method to solve the BBC NTV extension. A constraint was added to limit the number of ambulances assigned to a hub.

SALT_BBC_Utility_050420.py was used to solve the BBC utility extenstion.

the sample for solving the utility extension problem for charlottee is collected using sample_Charlotte_Utility_112619.py 
the sample for solving the NTV extension probelm for Hanover is collected using sample_Hanover_NTV_042720.py
