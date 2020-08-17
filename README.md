# MPC control for Solar-plus-Storage microgrid resilience

Author: Pol Boudou. Repository Master's Thesis project consisting in a MPC algorithm for microgrid control, dealing with grid outage uncertainty.

Repository cointains:
1) code for Energy Management System (EMS) simulation framework.
2) Jupyter notebook for resilience analysis of EMS simulation output.

When running a simulation, time-series from EMS simulation output ( have to be results will go to folder 'EMS_simulation/results_output'.

### To run a simulation, follow the following steps:

1) Download repository
2) Install Python modules 'numpy', 'pandas', 'scipy', 'datetime' and 'matplotlib'.
3) In '/resilience_MPC/EMS-simulation-scripts', run 'simulation.py'

**Changing simulation parameters:** 
- Simulation parameters can be changed in 'simulation.py' (simulation length, control timestep, outage forecast conditions, microgrid critical load and value of lost load (VoLL))
- Battery model parameters must be also changed in 'mpc_resilience.py'


