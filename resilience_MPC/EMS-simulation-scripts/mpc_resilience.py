#!/usr/bin/env python3
import pandas as pd
from datetime import timedelta
from datetime import datetime
from scipy.optimize import linprog

'''##############################################################################
##########                 MPC control algorithm                         ########
##############################################################################'''

# Battery model parameters:
STORAGE_RESERVE_FRACTION = 0.3

BATTERY_SOC_MAX = 38*1000                              			# in Watts-h
BATTERY_SOC_MIN = BATTERY_SOC_MAX*STORAGE_RESERVE_FRACTION      # in Watts-h
BATTERY_CHARGE_POWER_LIMIT = -8*1000                  			# in Watts
BATTERY_DISCHARGE_POWER_LIMIT = 8*1000                			# in Watts
BATTERY_POWER_EFFICIENCY = 0.95

# Control parameters:
TIME_SLOT = 1 					# in hours
HORIZON = 24 					# in HOURS


MPC_START_TIME = '02.08.2020 00:00:00'

no_slots = int(HORIZON / TIME_SLOT)


def get_load_forecast(iteration):
	df = pd.read_excel('../data_input/REopt_sizing_data/Resilient/clean_REopt_Load_Profile.xlsx', index_col=[0], usecols=[0,1])
	df['load (W)'] = df['Electricity:Facility [kW](Hourly)'] * -1000 # Convert (kW) to (W) and power convention (buy positive and sell negative)
	del df['Electricity:Facility [kW](Hourly)'] # we do not need the column anymore
	start_index = df.index[df.index == MPC_START_TIME][0] # df.index returns a list
	start_index += timedelta(hours=iteration)
	end_index = start_index + timedelta(hours = HORIZON - TIME_SLOT)
	load_forecast_df = df.loc[start_index:end_index]
	return load_forecast_df

def get_pv_power_forecast(iteration):
	df = pd.read_excel('../data_input/REopt_sizing_data/Resilient/clean_REopt_Load_Profile.xlsx', index_col=[0], usecols=[0,2])
	df['pv power'] = df['PV power (kW)'] * 1000 # Convert (kW) to (W) and power convention
	del df['PV power (kW)'] # we do not need the column anymore
	start_index = df.index[df.index == MPC_START_TIME][0] # df.index returns a list
	start_index += timedelta(hours=iteration)
	end_index = start_index + timedelta(hours = HORIZON - TIME_SLOT)
	pv_power_forecast_df = df.loc[start_index:end_index]
	return pv_power_forecast_df

def get_energy_sell_price():
	df = pd.read_excel('../data_input/energy_sell_price_10min_granularity.xlsx', index_col=[0], usecols=[0, 1])
	return df

def get_energy_buy_price():
	df = pd.read_excel('../data_input/energy_buy_price_10min_granularity.xlsx', index_col=[0], usecols=[0, 1])
	return df


def mpc_iteration(soc_measurement, iteration, prob_outage, duration_outage, crit_load, VoLL):

	duration_outage = int(duration_outage/TIME_SLOT)
	# Get disturbance forecasts
	# 1. Get excess solar power forecasts
	load_forecast_df = get_load_forecast(iteration)
	pv_forecast_df = get_pv_power_forecast(iteration)
	# Get energy sell price
	energy_sell_price_df = get_energy_sell_price()

	# Get energy buy price
	energy_buy_price_df = get_energy_buy_price()
	############ Set up the optimisation problem
	current_time = datetime.strptime(MPC_START_TIME, "%m.%d.%Y %H:%M:%S") + timedelta(hours=iteration)
	simu_time = current_time

	indices = []
	indices.append(current_time)

	NO_CTRL_VARS_PS = 8 # decision variables are (0)Epsilon, (1)Pg, (2)Pbat, (3)Ebat, (4)i-Pbat, (5)i-Ebat, (6)L_shed, (7)PV_shed, for each time slot
	no_ctrl_vars = NO_CTRL_VARS_PS * no_slots
	c = []
	bounds = [] # before passing to the OP, we'll convert it to a tuple (currently list because of frequent append operations)
	A_eq = []
	b_eq = []
	A_ub = []
	b_ub = []
	load = []
	pv = []
	net = []
	for x in range(no_slots):
		# 2. Setup the bounds for the control variables
		epsilon_bounds = (None, None)
		psg_bounds = (None, None)
		pbat_bounds = (BATTERY_CHARGE_POWER_LIMIT, BATTERY_DISCHARGE_POWER_LIMIT)
		ebat_bounds = (BATTERY_SOC_MIN, BATTERY_SOC_MAX)
		L_shed_bounds = (0, 1)
		PV_shed_bounds = (0, 1)
		bounds_one_slot = [epsilon_bounds, psg_bounds, pbat_bounds, ebat_bounds, pbat_bounds, ebat_bounds, L_shed_bounds, PV_shed_bounds]
		bounds.extend(bounds_one_slot)

		# 3. Setup equality constraints
		load_forecast_index = load_forecast_df.index[load_forecast_df.index == current_time][0] # df.index returns a list
		load_forecast = load_forecast_df.loc[load_forecast_index]
		load.append(load_forecast[0])
		pv_forecast_index = pv_forecast_df.index[pv_forecast_df.index == current_time][0] # df.index returns a list
		pv_forecast = pv_forecast_df.loc[pv_forecast_index]
		pv.append(pv_forecast[0])
		net.append(load_forecast[0]+pv_forecast[0])

		# grid-tied Battery model constraints
		row = [0] * no_ctrl_vars
		row[x * NO_CTRL_VARS_PS + 3] = 1
		row[x * NO_CTRL_VARS_PS + 2] = 1
		A_eq.append(row)
		if x == 0:
			b_eq.append(soc_measurement)
		else:
			row[x * NO_CTRL_VARS_PS - 5] = -1
			b_eq.append(0)

		# grid-tied power balance constraint
		row = [0] * no_ctrl_vars
		row[x * NO_CTRL_VARS_PS + 1] = 1 # variables are (0)Epsilon, (1)Pg, (2)Pbat, (3)Ebat, (4)i-Pbat, (5)i-Ebat, (6)L_shed, (7)PV_shed
		row[x * NO_CTRL_VARS_PS + 2] = 1
		A_eq.append(row)
		b_eq.append(-(pv_forecast[0] + load_forecast[0]))

		# islanded power balance constraint
		if x >= 1 and x <= duration_outage:
			row = [0] * no_ctrl_vars # (0)Epsilon, (1)Pg, (2)Pbat, (3)Ebat, (4)i-Pbat, (5)i-Ebat, (6)L_shed, (7)PV_shed
			row[x * NO_CTRL_VARS_PS + 4] = 1
			row[x * NO_CTRL_VARS_PS + 6] = - load_forecast[0]*crit_load
			row[x * NO_CTRL_VARS_PS + 7] = - pv_forecast[0]
			A_eq.append(row)
			#print("-(pv_forecast[0] + load_forecast[0]*crit_load)", -(pv_forecast[0] + load_forecast[0]*crit_load))
			b_eq.append(-(pv_forecast[0] + load_forecast[0]*crit_load))

		# islanded Battery model constraints
		row = [0] * no_ctrl_vars # (0)Epsilon, (1)Pg, (2)g-Pbat, (3)g-Ebat, (4)i-Pbat, (5)i-Ebat, (6)L_shed, (7)PV_shed
		row[x * NO_CTRL_VARS_PS + 5] = 1
		row[x * NO_CTRL_VARS_PS + 4] = 1
		A_eq.append(row)
		if x == 0:
			b_eq.append(soc_measurement)
		else:
			row[x * NO_CTRL_VARS_PS - 3] = -1
			b_eq.append(0)

		# 4. Setup inequality constraints
		sell_index = energy_sell_price_df.index[energy_sell_price_df.index == current_time][0] # dataframe.index returns a list
		buy_index = energy_buy_price_df.index[energy_buy_price_df.index == current_time][0] # df.index returns a list
		current_sell_price = energy_sell_price_df.loc[sell_index] # per unit energy price
		current_buy_price = energy_buy_price_df.loc[buy_index] # per unit (kWh) energy price
		# (0)Epsilon, (1)Pg, (2)g-Pbat, (3)g-Ebat, (4)i-Pbat, (5)i-Ebat, (6)L_shed, (7)PV_shed

		# SoC in grid-tied > SoC in islanded
		if prob_outage and (x >= 0) and (x < 1):
			row = [0] * no_ctrl_vars
			row[x * NO_CTRL_VARS_PS + 3] = 1
			row[x * NO_CTRL_VARS_PS + 5] = -1
			A_eq.append(row)
			b_eq.append(0)

		row = [0] * no_ctrl_vars
		row[x * NO_CTRL_VARS_PS] = -1
		row[x * NO_CTRL_VARS_PS + 1] = current_buy_price[0] / 1000 # converting it to price per Wh
		A_ub.append(row)
		b_ub.append(0)

		row = [0] * no_ctrl_vars
		row[x * NO_CTRL_VARS_PS] = -1
		row[x * NO_CTRL_VARS_PS + 1] = current_sell_price[0] / 1000 # converting it to price per Wh
		A_ub.append(row)
		b_ub.append(0)


		current_time = current_time + timedelta(hours = 1)
		indices.append(current_time)
		# Setup the objective function
		c.append(1-prob_outage)  # variables are (0)Epsilon, (1)Pg, (2)g-Pbat, (3)g-Ebat, (4)i-Pbat, (5)i-Ebat, (6)L_shed, (7)PV_shed
		c.extend([0, 0, 0, 0, 0.000, -(VoLL*0.001)*load_forecast[0]*prob_outage, 0.000])

	bounds = tuple(bounds)

	res = linprog(c, A_eq=A_eq, b_eq=b_eq, A_ub=A_ub, b_ub=b_ub, bounds=bounds, options={"disp": False, "maxiter": 50000, 'tol': 1e-6})

	x = 0
	output = {0: res.x[0], 1: -res.x[1], 2: res.x[2], 3: res.x[3], 4: res.x[4], 5: res.x[5], 6: res.x[6], 7: res.x[7]}

	return output




