from fastapi import FastAPI, UploadFile, Form
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pulp import *
from io import BytesIO
import shutil
import os

app = FastAPI(title="Energy Management System Optimizer API")

# Enable CORS for frontend (React/Vite)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# -----------------------------
# Utility function
# -----------------------------
def upsample_profile(hourly_profile, steps_per_hour, num_days):
    """Upsample hourly data using linear interpolation."""
    hourly_times = np.arange(len(hourly_profile))
    fine_times = np.linspace(0, len(hourly_profile) - 1, len(hourly_profile) * steps_per_hour)
    upsampled_single_day = np.interp(fine_times, hourly_times, hourly_profile).tolist()
    return upsampled_single_day * num_days


"""MILP-based optimizer aligned with the notebook.
Models grid import/export, diesel with min-power on/off, battery charge/discharge with SOC,
PV curtailment, and a simple hydrogen loop (electrolyzer piecewise efficiency + fuel cell).
Returns a detailed summary and a combined dispatch plot.
"""
def run_optimization(params, load_profile_24h, price_profile_24h):
    # Input validation
    try:
        num_days = max(1, min(30, int(params["num_days"])))  # Limit to 1-30 days
        time_resolution_minutes = int(params["time_resolution_minutes"])
        if time_resolution_minutes not in [15, 30, 60]:
            time_resolution_minutes = 30  # Default to 30 minutes
        
        grid_connection = max(100, float(params["grid_connection"]))  # kW, minimum 100kW
        solar_connection = max(0, float(params["solar_connection"]))  # kW
        battery_capacity_wh = max(1000, float(params["battery_capacity"]))  # Wh, minimum 1kWh
        battery_voltage = max(12, float(params["battery_voltage"]))  # V, minimum 12V
        diesel_capacity = max(0, float(params["diesel_capacity"]))  # kW
        fuel_price = max(0, float(params["fuel_price"]))  # INR/l
        pv_energy_cost = max(0, float(params["pv_energy_cost"]))  # INR/kWh
        load_curtail_cost = max(0, float(params["load_curtail_cost"]))  # INR/kWh
        battery_om_cost = max(0, float(params["battery_om_cost"]))  # INR/kWh
        weather = str(params["weather"]).lower()
        
        # Hydrogen system parameters (with defaults if not provided)
        electrolyzer_capacity = max(0, float(params.get("electrolyzer_capacity", 1000.0)))  # kW
        fuel_cell_capacity = max(0, float(params.get("fuel_cell_capacity", 800.0)))  # kW
        h2_tank_capacity = max(0, float(params.get("h2_tank_capacity", 100.0)))  # kg
        fuel_cell_efficiency_percent = max(0, min(1, float(params.get("fuel_cell_efficiency_percent", 0.60))))  # 0-1
        fuel_cell_om_cost = max(0, float(params.get("fuel_cell_om_cost", 1.5)))  # INR/kWh
        electrolyzer_om_cost = max(0, float(params.get("electrolyzer_om_cost", 0.5)))  # INR/kWh
        
        # Validate load and price profiles
        # Validate load and price profiles (allow multi-day or high-resolution data)
        if len(load_profile_24h) < 24:
            raise ValueError("Load profile must contain at least 24 data points")
        if len(price_profile_24h) < 24:
            raise ValueError("Price profile must contain at least 24 data points")

            
    except (ValueError, TypeError, KeyError) as e:
        raise ValueError(f"Invalid input parameters: {str(e)}")

    # Battery capacity: API receives Wh, convert to Ah for notebook compatibility
    # Notebook expects battery_capacity in Ah, but we're receiving Wh
    # So we convert: battery_capacity_wh = battery_capacity (from form) is in Wh
    battery_capacity_ah = battery_capacity_wh / battery_voltage  # Ah

    # Weather → solar scaling (matching notebook)
    wl = str(weather).lower()
    if wl == "sunny":
        solar_scale = 1.0
    elif wl == "cloudy":
        solar_scale = 0.6
    elif wl == "rainy":
        solar_scale = 0.3
    else:
        solar_scale = 1.0  # default to sunny

    # Hydrogen system constants (H2_LHV is fixed, not configurable)
    H2_LHV = 33.3  # kWh/kg

    step_size = time_resolution_minutes / 60.0
    steps_per_hour = int(60 / time_resolution_minutes)
    time_horizon = num_days * 24 * steps_per_hour

    # Solar profiles (matching notebook exactly)
    solar_profile_sunny = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.05, 0.2, 0.4, 0.6, 0.8, 0.9,
                           1.0, 0.95, 0.85, 0.7, 0.5, 0.25, 0.05, 0.0, 0.0, 0.0, 0.0, 0.0]
    solar_profile_rainy = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.01, 0.05, 0.1, 0.15, 0.2, 0.25, 
                           0.3, 0.25, 0.2, 0.15, 0.1, 0.05, 0.01, 0.0, 0.0, 0.0, 0.0, 0.0]
    
    # Select base profile based on weather
    if wl == "rainy":
        solar_profile_base = solar_profile_rainy
    else:
        solar_profile_base = solar_profile_sunny

    # # Upsample inputs to resolution and horizon
    # load_profile = upsample_profile(load_profile_24h, steps_per_hour, num_days)
    # price_profile = upsample_profile(price_profile_24h, steps_per_hour, num_days)
    # solar_profile = upsample_profile(solar_profile_base, steps_per_hour, num_days)

    # If data already matches expected total steps, skip upsampling
    expected_steps = num_days * 24 * steps_per_hour

    if len(load_profile_24h) == expected_steps:
        print(f"✅ Uploaded data already at {time_resolution_minutes}-min resolution. Skipping upsampling.")
        load_profile = load_profile_24h
        price_profile = price_profile_24h
    else:
        print(f"ℹ️ Upsampling base 24-hour profiles to {num_days} days × {time_resolution_minutes}-min resolution.")
        load_profile = upsample_profile(load_profile_24h, steps_per_hour, num_days)
        price_profile = upsample_profile(price_profile_24h, steps_per_hour, num_days)

    solar_profile = upsample_profile(solar_profile_base, steps_per_hour, num_days)


    # System capacities / derived values (matching notebook exactly)
    grid_max_power = grid_connection
    solar_capacity = solar_connection
    # Notebook: battery_storage_energy = (battery_capacity * battery_voltage) / 1000
    # Since we receive Wh, we convert: battery_storage_energy = battery_capacity_wh / 1000
    battery_storage_energy = battery_capacity_wh / 1000.0  # Convert Wh to kWh
    battery_power = battery_storage_energy * 0.5  # kW, 0.5C rate as in notebook
    bess_charge_capacity = battery_power
    bess_discharge_capacity = battery_power
    bess_energy_capacity = battery_storage_energy
    bess_min_soc, bess_max_soc = 0.1, 0.9
    bess_charge_efficiency, bess_discharge_efficiency = 0.95, 0.95

    diesel_min_power = 0.1 * diesel_capacity
    diesel_max_power = diesel_capacity
    fuel_slope, fuel_intercept = 0.18, 48  # l/kWh affine approx

    # Hydrogen parameters
    h2_min_soc, h2_max_soc = 0.1, 0.9
    fuel_cell_efficiency_kwh_per_kg = H2_LHV * fuel_cell_efficiency_percent
    fc_conversion_rate = 1.0 / max(1e-9, fuel_cell_efficiency_kwh_per_kg)

    # Piecewise electrolyzer efficiency (2-piece)
    P_break1_percent = 0.20
    eff_at_break1 = 0.80
    eff_at_break2 = 0.75
    P_break1 = electrolyzer_capacity * P_break1_percent
    P_break2 = electrolyzer_capacity
    H2_at_break1 = (P_break1 * eff_at_break1) / H2_LHV
    H2_at_break2 = (P_break2 * eff_at_break2) / H2_LHV
    slope_s1 = H2_at_break1 / P_break1 if P_break1 > 0 else 0
    slope_s2 = (H2_at_break2 - H2_at_break1) / (P_break2 - P_break1) if (P_break2 - P_break1) > 0 else 0
    width_s1 = P_break1
    width_s2 = P_break2 - P_break1

    # Model
    model = LpProblem('EMS_MILP', LpMinimize)
    T = range(time_horizon)

    # Decision variables
    P_grid = {t: LpVariable(f"P_grid_{t}", -grid_max_power, grid_max_power) for t in T}
    P_load_curt = {t: LpVariable(f"P_load_curt_{t}", 0) for t in T}
    P_diesel = {t: LpVariable(f"P_diesel_{t}", 0, diesel_max_power) for t in T}
    z_diesel = {t: LpVariable(f"z_diesel_{t}", cat='Binary') for t in T}
    F_diesel = {t: LpVariable(f"F_diesel_{t}", 0) for t in T}
    P_charge = {t: LpVariable(f"P_charge_{t}", 0, bess_charge_capacity) for t in T}
    P_discharge = {t: LpVariable(f"P_discharge_{t}", 0, bess_discharge_capacity) for t in T}
    E_battery = {t: LpVariable(f"E_battery_{t}", bess_min_soc * bess_energy_capacity, bess_max_soc * bess_energy_capacity) for t in T}
    z_bess = {t: LpVariable(f"z_bess_{t}", cat='Binary') for t in T}
    P_pv_used = {t: LpVariable(f"P_pv_used_{t}", 0) for t in T}
    P_solar_curt = {t: LpVariable(f"P_solar_curt_{t}", 0) for t in T}

    # Hydrogen side
    P_elec = {t: LpVariable(f"P_elec_{t}", 0, electrolyzer_capacity) for t in T}
    P_fc = {t: LpVariable(f"P_fc_{t}", 0, fuel_cell_capacity) for t in T}
    E_h2 = {t: LpVariable(f"E_h2_{t}", h2_min_soc * h2_tank_capacity, h2_max_soc * h2_tank_capacity) for t in T}
    z_h2 = {t: LpVariable(f"z_h2_{t}", cat='Binary') for t in T}
    P_elec_s1 = {t: LpVariable(f"P_elec_s1_{t}", 0, width_s1) for t in T}
    P_elec_s2 = {t: LpVariable(f"P_elec_s2_{t}", 0, width_s2) for t in T}
    z_elec_s2 = {t: LpVariable(f"z_elec_s2_{t}", cat='Binary') for t in T}
    H_produced = {t: LpVariable(f"H_produced_{t}", 0) for t in T}

    # Constraints
    for t in T:
        # Power balance
        load_served = load_profile[t] - P_load_curt[t]
        supply = P_pv_used[t] + P_diesel[t] + P_discharge[t] + P_grid[t] + P_fc[t]
        demand = load_served + P_charge[t] + P_elec[t]
        model += (supply == demand), f"power_balance_{t}"

    for t in T:
        # PV balance and curtailment
        solar_available = solar_profile[t] * solar_capacity
        model += P_pv_used[t] + P_solar_curt[t] == solar_available, f"pv_balance_{t}"

    for t in T:
        # Diesel min-up via on/off proxy and fuel consumption affine envelope
        model += P_diesel[t] >= diesel_min_power * z_diesel[t], f"diesel_min_{t}"
        model += P_diesel[t] <= diesel_max_power * z_diesel[t], f"diesel_max_{t}"
        model += F_diesel[t] >= fuel_slope * P_diesel[t] + fuel_intercept * z_diesel[t], f"fuel_cons_{t}"

    # Battery dynamics and no simultaneous charge/discharge
    initial_battery_level = 0.5 * bess_energy_capacity
    model += E_battery[0] == initial_battery_level
    for t in T:
        if t < time_horizon - 1:
            model += (
                E_battery[t+1] == E_battery[t] + step_size * (P_charge[t] * bess_charge_efficiency - P_discharge[t] * (1.0 / bess_discharge_efficiency))
            ), f"battery_dynamics_{t}"
        model += P_charge[t] <= bess_charge_capacity * (1 - z_bess[t]), f"charge_limit_{t}"
        model += P_discharge[t] <= bess_discharge_capacity * z_bess[t], f"discharge_limit_{t}"
    # Cyclic final SOC
    model += (
        initial_battery_level == E_battery[time_horizon-1] + step_size * (P_charge[time_horizon-1] * bess_charge_efficiency - P_discharge[time_horizon-1] * (1.0 / bess_discharge_efficiency))
    ), "battery_cyclic_soc"

    # Hydrogen dynamics with piecewise electrolyzer
    initial_h2_level = 0.5 * h2_tank_capacity
    model += E_h2[0] == initial_h2_level
    for t in T:
        model += P_elec[t] == P_elec_s1[t] + P_elec_s2[t], f"elec_sum_{t}"
        model += H_produced[t] == (P_elec_s1[t] * slope_s1) + (P_elec_s2[t] * slope_s2), f"h2_prod_{t}"
        model += P_elec_s1[t] >= width_s1 * z_elec_s2[t], f"elec_s1_before_s2_{t}"
        model += P_elec_s2[t] <= width_s2 * z_elec_s2[t], f"elec_s2_activation_{t}"
        model += P_fc[t] <= fuel_cell_capacity * z_h2[t], f"fc_limit_{t}"
        model += P_elec[t] <= electrolyzer_capacity * (1 - z_h2[t]), f"elec_limit_{t}"
        if t < time_horizon - 1:
            model += (
            E_h2[t+1] == E_h2[t] + H_produced[t] * step_size - (P_fc[t] * step_size * fc_conversion_rate)
            ), f"h2_dyn_{t}"
    model += (
        E_h2[0] == E_h2[time_horizon-1] + H_produced[time_horizon-1] * step_size - (P_fc[time_horizon-1] * step_size * fc_conversion_rate)
    ), "h2_cyclic"

    # Objective: cost of grid, curtailment penalty, diesel fuel, PV proxy, battery OM, and H2 operation costs
    # (matching notebook exactly)
    model += sum([
        step_size * price_profile[t] * P_grid[t]
        + step_size * load_curtail_cost * P_load_curt[t]
        + fuel_price * F_diesel[t]
        + step_size * pv_energy_cost * P_pv_used[t]
        + step_size * battery_om_cost * P_discharge[t]
        + step_size * fuel_cell_om_cost * P_fc[t]
        + step_size * electrolyzer_om_cost * P_elec[t]
        for t in T
    ])

    # Solve - Use system-installed CBC if available (ARM64 compatible), otherwise fall back to bundled
    cbc_path = shutil.which('cbc')
    if cbc_path:
        # Use system-installed CBC (fixes "Bad CPU type" error on Apple Silicon)
        os.environ['COIN_CMD'] = cbc_path
        solver = COIN_CMD(msg=0, timeLimit=180, gapRel=0.01)
        print(f"Using system CBC solver at: {cbc_path}")
    else:
        # Fall back to bundled CBC
        solver = PULP_CBC_CMD(msg=0, timeLimit=180, gapRel=0.01)
        print("Using bundled CBC solver")
    model.solve(solver)

    # Gather results (matching notebook structure exactly)
    time_hours = [t * step_size for t in T]
    
    # Calculate H2 levels at end of each time step (for plotting, matching notebook)
    h2_levels_for_plot = []
    for t in T:
        h2_at_end_of_t = value(E_h2[t]) + value(H_produced[t]) * step_size - value(P_fc[t]) * step_size * fc_conversion_rate
        h2_levels_for_plot.append(h2_at_end_of_t)
    
    results = {
        'Time_Step': list(range(time_horizon)),
        'Time_Hours': time_hours,
        'Load_Demand': load_profile,
        'Price': price_profile,
        'Grid_Power': [value(P_grid[t]) for t in T],
        'Load_Curtailed': [value(P_load_curt[t]) for t in T],
        'Diesel_Power': [value(P_diesel[t]) for t in T],
        'Fuel_Use_l': [value(F_diesel[t]) for t in T],  # Fuel consumption in liters per time step
        'Fuel_Cost': [fuel_price * value(F_diesel[t]) for t in T],  # Fuel cost per time step
        'Charge_Power': [value(P_charge[t]) for t in T],
        'Discharge_Power': [value(P_discharge[t]) for t in T],
        'Net_Battery_Power': [value(P_discharge[t]) - value(P_charge[t]) for t in T],
        'Battery_Level': [value(E_battery[t]) for t in T],
        'Battery_SOC': [value(E_battery[t]) / bess_energy_capacity * 100 for t in T],  # Battery SOC in %
        'Solar_Available': [solar_profile[t] * solar_capacity for t in T],
        'PV_Used': [value(P_pv_used[t]) for t in T],
        'Solar_Curtailed': [value(P_solar_curt[t]) for t in T],
        'Electrolyzer_Power': [value(P_elec[t]) for t in T],
        'Fuel_Cell_Power': [value(P_fc[t]) for t in T],
        'Net_H2_Power': [value(P_fc[t]) - value(P_elec[t]) for t in T],
        'H2_Level': h2_levels_for_plot,  # H2 level at end of each step
        'H2_SOC': [level / h2_tank_capacity * 100 for level in h2_levels_for_plot],  # H2 SOC in %
        'Fuel_Cell_OM_Cost': [fuel_cell_om_cost * value(P_fc[t]) * step_size for t in T],
        'H2_Produced_kg': [value(H_produced[t]) for t in T]  # H2 produced per time step
    }

    # Aggregates (matching notebook calculations)
    total_load = sum(load_profile) * step_size
    total_served = total_load - sum(results['Load_Curtailed']) * step_size
    grid_import = sum(max(0.0, p) for p in results['Grid_Power']) * step_size
    grid_export = sum(max(0.0, -p) for p in results['Grid_Power']) * step_size
    diesel_energy = sum(results['Diesel_Power']) * step_size
    fuel_cost_total = sum(results['Fuel_Use_l']) * fuel_price
    total_pv_used = sum(results['PV_Used']) * step_size
    total_pv_avail = sum(results['Solar_Available']) * step_size
    total_charge = sum(results['Charge_Power']) * step_size
    total_discharge = sum(results['Discharge_Power']) * step_size
    battery_om_total = total_discharge * battery_om_cost
    
    # Hydrogen system totals (matching notebook calculations)
    total_h2_produced_kwh_input = sum(results['Electrolyzer_Power']) * step_size
    total_h2_produced_kg = sum(results['H2_Produced_kg']) * step_size
    total_h2_consumed_kwh_output = sum(results['Fuel_Cell_Power']) * step_size
    total_h2_consumed_kg = total_h2_consumed_kwh_output * fc_conversion_rate
    fuel_cell_om_total = sum(results['Fuel_Cell_OM_Cost'])
    electrolyzer_om_total = total_h2_produced_kwh_input * electrolyzer_om_cost
    round_trip_efficiency_h2 = (total_h2_consumed_kwh_output / total_h2_produced_kwh_input * 100) if total_h2_produced_kwh_input > 0 else 0
    
    # Cost calculations (matching notebook)
    grid_cost = sum(max(0.0, results['Grid_Power'][t]) * price_profile[t] * step_size for t in range(time_horizon))
    pv_cost = total_pv_used * pv_energy_cost
    total_cost_value = value(model.objective)
    cost_per_kwh = (total_cost_value / total_served) if total_served > 0 else 0

    summary = {
        "Optimization_Period_days": num_days,
        "Resolution_min": time_resolution_minutes,
        "Weather": weather,
        "Load": {
            "Total_Demand_kWh": round(total_load, 2),
            "Total_Served_kWh": round(total_served, 2),
            "Served_Percent": round((total_served/total_load*100) if total_load>0 else 0, 1)
        },
        "Grid": {
            "Import_kWh": round(grid_import, 2), 
            "Export_kWh": round(grid_export, 2), 
            "Energy_Cost_INR": round(grid_cost, 2)
        },
        "Diesel": {
            "Energy_kWh": round(diesel_energy, 2), 
            "Fuel_Cost_INR": round(fuel_cost_total, 2)
        },
        "Battery": {
            "Charged_kWh": round(total_charge, 2),
            "Discharged_kWh": round(total_discharge, 2), 
            "OM_Cost_INR": round(battery_om_total, 2)
        },
        "Solar": {
            "Available_kWh": round(total_pv_avail, 2),
            "Used_kWh": round(total_pv_used, 2),
            "Used_Percent": round((total_pv_used/total_pv_avail*100) if total_pv_avail>0 else 0, 1)
        },
        "Hydrogen": {
            "Energy_to_Electrolyzer_kWh": round(total_h2_produced_kwh_input, 2),
            "Energy_from_Fuel_Cell_kWh": round(total_h2_consumed_kwh_output, 2),
            "Hydrogen_Produced_kg": round(total_h2_produced_kg, 2),
            "Hydrogen_Consumed_kg": round(total_h2_consumed_kg, 2),
            "Fuel_Cell_OM_Cost_INR": round(fuel_cell_om_total, 2),
            "Electrolyzer_OM_Cost_INR": round(electrolyzer_om_total, 2),
            "Round_Trip_Efficiency_percent": round(round_trip_efficiency_h2, 1),
            "Effective_Conversion_kWh_per_kg": round(total_h2_produced_kwh_input/total_h2_produced_kg if total_h2_produced_kg > 0 else 0, 2)
        },
        "Costs": {
            "Grid_Cost_INR": round(grid_cost, 2),
            "Diesel_Fuel_Cost_INR": round(fuel_cost_total, 2),
            "PV_Energy_Cost_INR": round(pv_cost, 2),
            "Battery_OM_Cost_INR": round(battery_om_total, 2),
            "Fuel_Cell_OM_Cost_INR": round(fuel_cell_om_total, 2),
            "Electrolyzer_OM_Cost_INR": round(electrolyzer_om_total, 2),
            "TOTAL_COST_INR": round(total_cost_value, 2),
            "Cost_per_kWh_INR": round(cost_per_kwh, 2),
        }
    }

    # Generate all plots (matching notebook exactly)
    plt.style.use('seaborn-v0_8-whitegrid')
    plt.rcParams.update({'font.size': 14, 'font.family': 'serif', 'axes.labelweight': 'bold', 'axes.titleweight': 'bold'})
    colors = {'load': "#010103", 'grid': "#0863D1", 'diesel': "#72394F", 'battery': "#8938F3", 'solar': "#6BF520", 'h2': "#17becf", 'price': "#CA3510", 'cost': "#25E8F3"}
    
    # Create a figure with 3 subplots (vertical layout)
    fig = plt.figure(figsize=(10, 18))
    
    # Plot 1: Power Dispatch Strategy
    ax1 = plt.subplot(3, 1, 1)
    ax1.plot(results['Time_Hours'], results['Load_Demand'], color=colors['load'], label='Load Demand', linewidth=3, markersize=6, markerfacecolor='white', markeredgewidth=2, markevery=max(1, len(results['Time_Hours'])//100))
    ax1.plot(results['Time_Hours'], results['Grid_Power'], color=colors['grid'], label='Grid Power', linewidth=2.5, markersize=5, alpha=0.8, markevery=max(1, len(results['Time_Hours'])//100))
    ax1.plot(results['Time_Hours'], results['Diesel_Power'], color=colors['diesel'], label='Diesel Gen', linewidth=2.5, markersize=5, alpha=0.8, markevery=max(1, len(results['Time_Hours'])//100))
    ax1.plot(results['Time_Hours'], results['PV_Used'], color=colors['solar'], label='Solar PV', linewidth=2.5, markersize=5, alpha=0.8, markevery=max(1, len(results['Time_Hours'])//100))
    ax1.plot(results['Time_Hours'], results['Net_Battery_Power'], color=colors['battery'], label='Battery Power', linewidth=2.5, markersize=5, alpha=0.8, markevery=max(1, len(results['Time_Hours'])//100))
    ax1.plot(results['Time_Hours'], results['Net_H2_Power'], color=colors['h2'], label='Hydrogen Sys Power', linewidth=2.5, markersize=6, alpha=0.8, markevery=max(1, len(results['Time_Hours'])//100))
    ax1.set_title(f'Optimal Power Dispatch Strategy ({num_days} Day{"s" if num_days > 1 else ""}, {time_resolution_minutes}-min resolution)', fontsize=16, pad=20, fontweight='bold')
    ax1.set_xlabel('Time [hours]', fontsize=14)
    ax1.set_ylabel('Power [kW]', fontsize=14)
    ax1.legend(loc='upper right', fontsize=10, framealpha=0.9, ncol=3)
    ax1.grid(True, alpha=0.3)
    ax1.set_xlim(-0.5, num_days * 24 + 0.5)
    
    # Calculate Y-axis range from -min to +max with margin
    # Get all power values to find min and max
    all_power_values = []
    all_power_values.extend(results['Load_Demand'])
    all_power_values.extend(results['Grid_Power'])
    all_power_values.extend(results['Diesel_Power'])
    all_power_values.extend(results['PV_Used'])
    all_power_values.extend(results['Net_Battery_Power'])
    all_power_values.extend(results['Net_H2_Power'])
    
    min_power = min(all_power_values)
    max_power = max(all_power_values)
    margin = max(abs(min_power), abs(max_power)) * 0.1  # 10% margin
    ax1.set_ylim(min_power - margin, max_power + margin)
    
    # Plot 2: Battery State of Charge
    ax2 = plt.subplot(3, 1, 2)
    ax2.plot(results['Time_Hours'], results['Battery_SOC'], color=colors['battery'], linewidth=4, markersize=6, markerfacecolor='white', markeredgewidth=3, markevery=max(1, len(results['Time_Hours'])//100))
    ax2.axhline(y=bess_min_soc*100, color='red', linestyle='--', alpha=0.7, linewidth=2, label=f'Min SOC ({bess_min_soc*100:.0f}%)')
    ax2.axhline(y=bess_max_soc*100, color='green', linestyle='--', alpha=0.7, linewidth=2, label=f'Max SOC ({bess_max_soc*100:.0f}%)')
    ax2.fill_between(results['Time_Hours'], bess_min_soc*100, bess_max_soc*100, alpha=0.1, color=colors['battery'])
    ax2.set_title(f'Battery State of Charge ({num_days} Day{"s" if num_days > 1 else ""})', fontsize=16, pad=20)
    ax2.set_xlabel('Time [hours]', fontsize=14)
    ax2.set_ylabel('State of Charge [%]', fontsize=14)
    ax2.set_ylim(-5, 105)
    ax2.set_xlim(-0.5, num_days * 24 + 0.5)
    ax2.grid(True, alpha=0.3)
    ax2.legend(fontsize=12, framealpha=0.9, loc='upper right')
    
    # Plot 3: Hydrogen Storage Level
    ax3 = plt.subplot(3, 1, 3)
    ax3.plot(results['Time_Hours'], results['H2_SOC'], color=colors['h2'], linewidth=4, markersize=7, markerfacecolor='white', markeredgewidth=3, markevery=max(1, len(results['Time_Hours'])//100))
    ax3.axhline(y=h2_min_soc*100, color='red', linestyle='--', alpha=0.7, linewidth=2, label=f'Min Level ({h2_min_soc*100:.0f}%)')
    ax3.axhline(y=h2_max_soc*100, color='green', linestyle='--', alpha=0.7, linewidth=2, label=f'Max Level ({h2_max_soc*100:.0f}%)')
    ax3.fill_between(results['Time_Hours'], h2_min_soc*100, h2_max_soc*100, alpha=0.1, color=colors['h2'])
    ax3.set_title(f'Hydrogen Storage Level ({num_days} Day{"s" if num_days > 1 else ""})', fontsize=16, pad=20)
    ax3.set_xlabel('Time [hours]', fontsize=14)
    ax3.set_ylabel('Hydrogen Stored [% of Capacity]', fontsize=14)
    ax3.set_ylim(-5, 105)
    ax3.set_xlim(-0.5, num_days * 24 + 0.5)
    ax3.grid(True, alpha=0.3)
    ax3.legend(fontsize=12, framealpha=0.9, loc='upper right')
    
    plt.tight_layout()
    buf = BytesIO()
    plt.savefig(buf, format="png", dpi=150, bbox_inches='tight')
    buf.seek(0)
    plot_bytes = buf.read()
    plt.close()

    return summary, plot_bytes


# # -----------------------------
# # FastAPI Endpoints
# # -----------------------------
# @app.post("/optimize")
# async def optimize(
#     file: UploadFile = None,
#     profile_type: str = Form("Auto detect"),
#     weather: str = Form("Sunny"),
#     num_days: int = Form(2),
#     time_resolution_minutes: int = Form(30),
#     grid_connection: float = Form(2000),
#     solar_connection: float = Form(2000),
#     battery_capacity: float = Form(80000),  # Wh (matching notebook default)
#     battery_voltage: float = Form(100),
#     diesel_capacity: float = Form(2200),
#     fuel_price: float = Form(95),
#     pv_energy_cost: float = Form(2.95),  # Matching notebook
#     load_curtail_cost: float = Form(50),
#     battery_om_cost: float = Form(0.085)  # Matching notebook
# ):
#     # Default load and price
#     load_profile_24h = [800, 750, 700, 650, 600, 650, 750, 850, 950, 1100, 1200,
#                         1300, 1250, 1200, 1150, 1200, 1300, 1400, 1500, 1450, 1300, 1150, 1000, 900]
#     price_profile_24h = [3.5, 3.2, 3.0, 2.8, 2.5, 2.8, 4.2, 5.5, 6.2, 7.8, 8.5,
#                          9.2, 8.8, 8.2, 7.5, 8.0, 8.8, 9.5, 10.2, 9.8, 8.5, 7.2, 5.5, 4.2]

#     # # If file is uploaded, read data
#     # if file:
#     #     df = pd.read_csv(BytesIO(await file.read()))
#     #     if "Load (kW)" in df.columns:
#     #         load_profile_24h = df["Load (kW)"].tolist()
#     #     if "Price (INR/kWh)" in df.columns:
#     #         price_profile_24h = df["Price (INR/kWh)"].tolist()


#     # params = {
#     #     "num_days": num_days,
#     #     "time_resolution_minutes": time_resolution_minutes,
#     #     "grid_connection": grid_connection,
#     #     "solar_connection": solar_connection,
#     #     "battery_capacity": battery_capacity,
#     #     "battery_voltage": battery_voltage,
#     #     "diesel_capacity": diesel_capacity,
#     #     "fuel_price": fuel_price,
#     #     "pv_energy_cost": pv_energy_cost,
#     #     "load_curtail_cost": load_curtail_cost,
#     #     "battery_om_cost": battery_om_cost,
#     #     "weather": weather
#     # }

#     # If file is uploaded, read data
#     # if file:
#     #     df = pd.read_csv(BytesIO(await file.read()))

#     #     # Extract load/price columns
#     #     if "Load" in df.columns:
#     #         load_profile_24h = df["Load"].tolist()
#     #     elif "Load (kW)" in df.columns:
#     #         load_profile_24h = df["Load (kW)"].tolist()

#     #     if "Price" in df.columns:
#     #         price_profile_24h = df["Price"].tolist()
#     #     elif "Price (INR/kWh)" in df.columns:
#     #         price_profile_24h = df["Price (INR/kWh)"].tolist()
#     # If file is uploaded, read data
#     if file:
#         df = pd.read_csv(BytesIO(await file.read()))

#         # --- Case 1: CSV contains Timestamp column (full time-series synthetic data) ---
#         if "Timestamp" in df.columns:
#             # Infer duration dynamically
#             df["Timestamp"] = pd.to_datetime(df["Timestamp"])
#             df = df.sort_values("Timestamp")

#             # Infer resolution from first two timestamps
#             inferred_resolution = (df["Timestamp"].iloc[1] - df["Timestamp"].iloc[0]).seconds / 60
#             time_resolution_minutes = int(inferred_resolution)

#             # Infer total days
#             total_minutes = (df["Timestamp"].iloc[-1] - df["Timestamp"].iloc[0]).total_seconds() / 60
#             inferred_days = max(1, round(total_minutes / (24 * 60)))
#             num_days = inferred_days

#             # Extract directly from file
#             load_profile_full = df.iloc[:, df.columns.str.contains("Load", case=False)].squeeze().tolist()
#             price_profile_full = df.iloc[:, df.columns.str.contains("Price", case=False)].squeeze().tolist()

#             # Override 24-hour validation → Pass full arrays
#             load_profile_24h = load_profile_full
#             price_profile_24h = price_profile_full

#             print(f"📂 Using uploaded file with inferred {num_days} day(s) and {time_resolution_minutes}-minute resolution")

#         # --- Case 2: Simple 24-hour CSV ---
#         elif any("Load" in c for c in df.columns):
#             load_profile_24h = df.iloc[:, df.columns.str.contains("Load", case=False)].squeeze().tolist()
#             price_profile_24h = df.iloc[:, df.columns.str.contains("Price", case=False)].squeeze().tolist()

#         else:
#             raise ValueError("CSV must contain 'Load' and 'Price' columns")


#         # ---- NEW: dynamically infer number of days ----
#         if "Timestamp" in df.columns:
#             try:
#                 df["Timestamp"] = pd.to_datetime(df["Timestamp"])
#                 total_minutes = (df["Timestamp"].iloc[-1] - df["Timestamp"].iloc[0]).total_seconds() / 60
#                 inferred_days = max(1, round(total_minutes / (24 * 60)))
#                 num_days = inferred_days
#             except Exception as e:
#                 print(f"⚠ Could not infer duration from timestamps: {e}")
#         else:
#             # If timestamp missing, infer from row count
#             records_per_day = int(24 * (60 / time_resolution_minutes))
#             inferred_days = max(1, round(len(df) / records_per_day))
#             num_days = inferred_days

#         print(f"📊 Inferred duration from uploaded file: {num_days} day(s)")

#     # ---------------------
#     # Keep parameters synced
#     # ---------------------
#     params = {
#         "num_days": num_days,
#         "time_resolution_minutes": time_resolution_minutes,
#         "grid_connection": grid_connection,
#         "solar_connection": solar_connection,
#         "battery_capacity": battery_capacity,
#         "battery_voltage": battery_voltage,
#         "diesel_capacity": diesel_capacity,
#         "fuel_price": fuel_price,
#         "pv_energy_cost": pv_energy_cost,
#         "load_curtail_cost": load_curtail_cost,
#         "battery_om_cost": battery_om_cost,
#         "weather": weather
#     }

#     try:
#         summary, plot_bytes = run_optimization(params, load_profile_24h, price_profile_24h)
#         return JSONResponse({"status": "success", "summary": summary})
#     except ValueError as e:
#         return JSONResponse({"status": "error", "message": str(e)}, status_code=400)
#     except Exception as e:
#         return JSONResponse({"status": "error", "message": f"Optimization failed: {str(e)}"}, status_code=500)

# -----------------------------
# FastAPI Endpoints
# -----------------------------
@app.post("/optimize")
async def optimize(
    file: UploadFile = None,
    profile_type: str = Form("Auto detect"),
    weather: str = Form("Sunny"),
    num_days: int = Form(2),
    time_resolution_minutes: int = Form(30),
    grid_connection: float = Form(2000),
    solar_connection: float = Form(2000),
    battery_capacity: float = Form(4000000),  # Wh (matching notebook: 40000 Ah * 100V = 4000000 Wh)
    battery_voltage: float = Form(100),
    diesel_capacity: float = Form(2200),
    fuel_price: float = Form(95),
    pv_energy_cost: float = Form(2.85),  # Matching notebook
    load_curtail_cost: float = Form(50),
    battery_om_cost: float = Form(6.085)  # Matching notebook
):
    """
    Unified EMS optimization endpoint:
    - Accepts uploaded CSV or uses default 24-hour base profiles
    - Automatically infers duration (days) from uploaded file
    - Returns JSON summary + Base64-encoded plot in one response
    """

    import base64
    import pandas as pd
    from io import BytesIO

    # -----------------------------
    # Default 24-hour profiles (fallback - matching notebook)
    # -----------------------------
    load_profile = [800, 750, 700, 650, 600, 650, 750, 850, 950, 1100, 1200, 1300,
                    1250, 1200, 1150, 1200, 1300, 1400, 1500, 1450, 1300, 1150, 1000, 900]
    price_profile = [3.5, 3.2, 3.0, 2.8, 2.5, 2.8, 4.2, 5.5, 6.2, 7.8, 8.5,
                     9.2, 8.8, 8.2, 7.5, 8.0, 8.8, 9.5, 10.2, 9.8, 8.5, 7.2, 5.5, 4.2]

    inferred_days = num_days  # default to user input

    # -----------------------------
    # Handle uploaded CSV
    # -----------------------------
    if file:
        df = pd.read_csv(BytesIO(await file.read()))

        # Check for datetime/timestamp columns (case-insensitive)
        datetime_col = None
        for col in df.columns:
            if col.lower() in ['timestamp', 'datetime', 'date', 'time']:
                datetime_col = col
                break

        if datetime_col:
            df[datetime_col] = pd.to_datetime(df[datetime_col])
            df = df.sort_values(datetime_col)

            # Infer resolution and duration
            inferred_resolution = (df[datetime_col].iloc[1] - df[datetime_col].iloc[0]).seconds / 60
            time_resolution_minutes = int(inferred_resolution)
            total_minutes = (df[datetime_col].iloc[-1] - df[datetime_col].iloc[0]).total_seconds() / 60
            inferred_days = max(1, round(total_minutes / (24 * 60)))

            print(f"📂 Using uploaded file with inferred {inferred_days} day(s) and {time_resolution_minutes}-minute resolution")

        # Extract load/price columns (case-insensitive)
        load_profile = df.iloc[:, df.columns.str.contains("Load", case=False)].squeeze().tolist()
        price_profile = df.iloc[:, df.columns.str.contains("Price", case=False)].squeeze().tolist()

        # Fallback: infer days if timestamp missing
        if not datetime_col:
            records_per_day = int(24 * (60 / time_resolution_minutes))
            inferred_days = max(1, round(len(df) / records_per_day))
            print(f"📊 Inferred duration from row count: {inferred_days} day(s)")

    # -----------------------------
    # Build Parameters
    # -----------------------------
    params = {
        "num_days": inferred_days,
        "time_resolution_minutes": time_resolution_minutes,
        "grid_connection": grid_connection,
        "solar_connection": solar_connection,
        "battery_capacity": battery_capacity,
        "battery_voltage": battery_voltage,
        "diesel_capacity": diesel_capacity,
        "fuel_price": fuel_price,
        "pv_energy_cost": pv_energy_cost,
        "load_curtail_cost": load_curtail_cost,
        "battery_om_cost": battery_om_cost,
        "weather": weather
    }

    # -----------------------------
    # Run Optimization + Generate Plot
    # -----------------------------
    try:
        summary, plot_bytes = run_optimization(params, load_profile, price_profile)

        # Convert image bytes → base64 for direct UI rendering
        plot_base64 = base64.b64encode(plot_bytes).decode("utf-8")

        return JSONResponse({
            "status": "success",
            "summary": summary,
            "plot_base64": plot_base64
        })

    except ValueError as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=400)
    except Exception as e:
        return JSONResponse({"status": "error", "message": f"Optimization failed: {str(e)}"}, status_code=500)

@app.post("/optimize/plot")
async def optimize_with_plot(
    weather: str = Form("Sunny"),
    num_days: int = Form(2),
    time_resolution_minutes: int = Form(30)
):
    params = {
        "num_days": num_days,
        "time_resolution_minutes": time_resolution_minutes,
        "grid_connection": 2000,
        "solar_connection": 2000,
        "battery_capacity": 4000000,  # Wh (matching notebook: 40000 Ah * 100V = 4000000 Wh)
        "battery_voltage": 100,
        "diesel_capacity": 2200,
        "fuel_price": 95,
        "pv_energy_cost": 2.85,
        "load_curtail_cost": 50,
        "battery_om_cost": 6.085,
        "weather": weather
    }

    load_profile_24h = [800, 750, 700, 650, 600, 650, 750, 850, 950, 1100, 1200, 1300,
                        1250, 1200, 1150, 1200, 1300, 1400, 1500, 1450, 1300, 1150, 1000, 900]
    price_profile_24h = [3.5, 3.2, 3.0, 2.8, 2.5, 2.8, 4.2, 5.5, 6.2, 7.8, 8.5,
                         9.2, 8.8, 8.2, 7.5, 8.0, 8.8, 9.5, 10.2, 9.8, 8.5, 7.2, 5.5, 4.2]

    try:
        _, plot_bytes = run_optimization(params, load_profile_24h, price_profile_24h)
        return StreamingResponse(BytesIO(plot_bytes), media_type="image/png")
    except ValueError as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=400)
    except Exception as e:
        return JSONResponse({"status": "error", "message": f"Plot generation failed: {str(e)}"}, status_code=500)


@app.get("/")
async def home():
    return {"message": "✅ EMS Optimizer FastAPI is running"}


# -----------------------------
# Run locally:  uvicorn ems_api:app --reload
# -----------------------------
