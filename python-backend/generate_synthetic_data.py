"""
generate_synthetic_data.py
--------------------------
Generates synthetic load, price, and solar data for Energy Management System (EMS).

✅ Features:
- Simulates daily load demand curves (morning + evening peaks)
- Adds 5–15% randomness across days and time steps with weather-specific variations
- Supports multiple days and weather modes (Sunny / Rainy / Cloudy) with distinct patterns
- Can automatically create multiple test datasets for validation
- Saves each dataset as CSV file compatible with EMS FastAPI input
- Enhanced with AR(1) noise for realistic temporal patterns

Usage:
    # Single dataset
    python generate_synthetic_data.py --days 5 --resolution 30 --weather Sunny

    # Generate multiple test sets
    python generate_synthetic_data.py --generate_tests
"""

import numpy as np
import pandas as pd
import argparse
from datetime import datetime, timedelta
import os
import random

# -----------------------------
# Utility Functions
# -----------------------------

def add_randomness(data, variation_percent=0.1):
    """Add ±variation_percent randomness (element-wise) to a numeric array."""
    noise_factor = np.random.uniform(1 - variation_percent, 1 + variation_percent, len(data))
    return np.clip(data * noise_factor, 0, None)  # keep non-negative

def generate_ar1_noise(length, phi, sigma, initial_noise=None):
    """Generate AR(1) noise with given correlation (phi) and standard deviation (sigma)."""
    if initial_noise is None:
        initial_noise = np.random.normal(0, sigma)
    noise = np.zeros(length)
    noise[0] = initial_noise
    for i in range(1, length):
        noise[i] = phi * noise[i-1] + np.random.normal(0, sigma * np.sqrt(1 - phi**2))
    return noise

def generate_load_profile(num_days: int, steps_per_hour: int):
    """Generate synthetic residential/commercial load pattern with randomness and AR(1) correlation."""
    hours = np.arange(0, 24, 1 / steps_per_hour)
    base_profile = (
        500
        + 300 * np.sin((hours - 7) / 24 * 2 * np.pi) ** 2  # morning rise
        + 400 * np.sin((hours - 18) / 24 * 2 * np.pi) ** 4  # evening peak
    )

    load_profile = []
    phi = 0.8  # AR(1) coefficient for temporal correlation
    sigma = 25  # Std dev of innovation term

    for d in range(num_days):
        day_variation = np.random.normal(1.0, 0.05)
        noise = generate_ar1_noise(len(base_profile), phi, sigma)
        day_profile = base_profile * day_variation + noise
        day_profile = add_randomness(day_profile, variation_percent=0.1)
        load_profile.extend(np.clip(day_profile, 300, 1600))

    return np.round(load_profile, 2)

def generate_price_profile(num_days: int, steps_per_hour: int):
    """Generate synthetic electricity price with daily and random peaks, plus AR(1) correlation."""
    hours = np.arange(0, 24, 1 / steps_per_hour)
    base_price = (
        3
        + 2.5 * np.sin((hours - 10) / 24 * 2 * np.pi) ** 2
        + 3.0 * np.sin((hours - 18) / 24 * 2 * np.pi) ** 6
    )

    price_profile = []
    phi = 0.7
    sigma = 0.15

    for d in range(num_days):
        daily_shift = np.random.uniform(-0.2, 0.2)
        noise = generate_ar1_noise(len(base_price), phi, sigma)  # Fixed: use base_price
        day_price = base_price + daily_shift + noise
        day_price = add_randomness(day_price, variation_percent=0.05)
        price_profile.extend(np.clip(day_price, 2.5, 10.5))

    return np.round(price_profile, 2)

def generate_solar_profile(num_days: int, steps_per_hour: int, weather: str):
    """Generate normalized solar irradiance profile (0 to 1) with weather-specific randomness and AR(1) correlation."""
    hours = np.arange(0, 24, 1 / steps_per_hour)
    base_curve = np.exp(-((hours - 12) ** 2) / 10)  # Base Gaussian peak at noon
    base_curve /= base_curve.max()

    # Weather-specific multipliers and noise parameters
    if weather.lower() == "sunny":
        multiplier = 1.0
        phi = 0.9  # High persistence for clear skies
        sigma = 0.03  # Low noise for stable sunny days
        variation_percent = 0.05  # 5% variation
    elif weather.lower() == "rainy":
        multiplier = 0.35
        phi = 0.6  # Lower persistence for erratic rainy patterns
        sigma = 0.1  # Higher noise for frequent drops
        variation_percent = 0.15  # 15% variation
    else:  # cloudy
        multiplier = 0.7
        phi = 0.75  # Moderate persistence for intermittent clouds
        sigma = 0.07  # Moderate noise for variable cloud cover
        variation_percent = 0.1  # 10% variation

    solar_profile = []
    for d in range(num_days):
        # Random daily shift in peak time (e.g., clouds moving)
        peak_shift = np.random.uniform(-2, 2)
        shifted_curve = np.exp(-((hours - (12 + peak_shift)) ** 2) / 10)
        shifted_curve /= shifted_curve.max()
        daily_scale = np.random.normal(multiplier, 0.05)

        # Apply weather-specific distortions
        if weather.lower() == "rainy":
            # Simulate rain-induced dips (random low periods)
            dips = np.random.choice([0, 1], size=len(hours), p=[0.7, 0.3])
            shifted_curve = shifted_curve * (1 - 0.5 * dips)
        elif weather.lower() == "cloudy":
            # Simulate intermittent cloud cover (random moderate dips)
            clouds = np.random.normal(0, 0.2, size=len(hours))
            shifted_curve = np.clip(shifted_curve * (1 + clouds), 0, 1)

        day_profile = np.clip(shifted_curve * daily_scale, 0, 1)
        noise = generate_ar1_noise(len(day_profile), phi, sigma)
        day_profile += noise
        day_profile = add_randomness(day_profile, variation_percent=variation_percent)
        solar_profile.extend(np.round(np.clip(day_profile, 0, 1), 3))

    return solar_profile

# -----------------------------
# Main Generator
# -----------------------------

def generate_synthetic_dataset(num_days=2, resolution=30, weather="Sunny", output_dir="synthetic_data"):
    steps_per_hour = int(60 / resolution)
    total_steps = num_days * 24 * steps_per_hour
    start_time = datetime.now().replace(minute=0, second=0, microsecond=0)

    load = generate_load_profile(num_days, steps_per_hour)
    price = generate_price_profile(num_days, steps_per_hour)
    solar = generate_solar_profile(num_days, steps_per_hour, weather)

    timestamps = [start_time + timedelta(minutes=resolution * i) for i in range(total_steps)]

    df = pd.DataFrame({
        "Timestamp": timestamps,
        "Load (kW)": load,
        "Price (INR/kWh)": price,
        "Solar (pu)": solar,
        "Weather": [weather] * total_steps
    })

    os.makedirs(output_dir, exist_ok=True)
    filename = f"{output_dir}/synthetic_data_{weather}_{num_days}d_{resolution}min.csv"
    df.to_csv(filename, index=False)

    print(f"\n✅ Synthetic data generated successfully!")
    print(f"   File saved at: {filename}")
    print(f"   Total records: {len(df)} rows")
    print(f"   Weather: {weather}, Duration: {num_days} days, Resolution: {resolution} min")
    print(f"   Random variation applied: 5–15% with weather-specific AR(1) correlation\n")
    return df

# -----------------------------
# Multiple Test Case Generator
# -----------------------------

def generate_multiple_test_cases():
    """Generate multiple CSVs for combinations of weather and duration."""
    test_configs = [
        {"days": 1, "weather": "Sunny"},
        {"days": 3, "weather": "Cloudy"},
        {"days": 5, "weather": "Rainy"},
        {"days": 7, "weather": "Sunny"},
        {"days": 10, "weather": "Cloudy"},
    ]

    resolution = 30  # fixed for simplicity, can be looped too
    print("\n🚀 Generating multiple synthetic test datasets...\n")
    for cfg in test_configs:
        generate_synthetic_dataset(num_days=cfg["days"], resolution=resolution, weather=cfg["weather"])
    print("✅ All test cases generated successfully!\n")

# -----------------------------
# CLI Entry Point
# -----------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate synthetic load & price data for EMS")
    parser.add_argument("--days", type=int, default=2, help="Number of days to simulate")
    parser.add_argument("--resolution", type=int, default=30, help="Time step in minutes (e.g., 15, 30, 60)")
    parser.add_argument("--weather", type=str, default="Sunny", help="Weather condition: Sunny / Rainy / Cloudy")
    parser.add_argument("--generate_tests", action="store_true", help="Generate multiple test CSVs for all scenarios")

    args = parser.parse_args()

    if args.generate_tests:
        generate_multiple_test_cases()
    else:
        generate_synthetic_dataset(num_days=args.days, resolution=args.resolution, weather=args.weather)