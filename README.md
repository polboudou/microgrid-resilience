# MPC control for enhanced resilience of Solar-plus-Storage microgrids

Author: Pol Boudou.

Repository containing scripts for Master's Thesis project "Optimal Control of Solar-plus-Storage microgrids for enhanced Resilience against Grid Outages"

Repository cointains:
1) codes for Energy Management System (EMS) simulation framework (\EMS-simulation-scripts)
2) Jupyter notebook for resilience analysis of EMS simulation output (outage_analysis.py)

When running a simulation, time-series obtained from EMS simulation must be transferred to Jupyter notebook 'outage_analysis.py'.

### To run a simulation, follow the following steps:

1) Download repository
2) Install Python modules 'numpy', 'pandas', 'scipy', 'datetime' and 'matplotlib'.
3) In '/resilience_MPC/EMS-simulation-scripts', run 'simulation.py'

**Changing simulation parameters:** 
- Simulation parameters can be changed in 'simulation.py' (simulation length, control timestep, outage forecast conditions, microgrid critical load and value of lost load (VoLL))
- If changing battery model parameters, the same parameters must be also updated in MPC algorithm 'mpc_resilience.py'.


