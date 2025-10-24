const mongoose = require("mongoose");

const userSchema = new mongoose.Schema({
  name: { type: String, required: true },
  email: { type: String, required: true },
  appliances: {
    type: Map,
    of: {
      low: { rating: Number, number: Number, hoursUsed: Number, total: Number },
      medium: {
        rating: Number,
        number: Number,
        hoursUsed: Number,
        total: Number,
      },
      high: {
        rating: Number,
        number: Number,
        hoursUsed: Number,
        total: Number,
      },
      other: {
        rating: Number,
        number: Number,
        hoursUsed: Number,
        total: Number,
      },
    },
  },
  misc: [
    {
      name: String,
      low: { rating: Number, number: Number, hoursUsed: Number, total: Number },
      medium: {
        rating: Number,
        number: Number,
        hoursUsed: Number,
        total: Number,
      },
      high: {
        rating: Number,
        number: Number,
        hoursUsed: Number,
        total: Number,
      },
      other: {
        rating: Number,
        number: Number,
        hoursUsed: Number,
        total: Number,
      },
    },
  ],
  choices: {
    energySource: [String],
    dieselUse: String,
    energyGoal: String,
  },
  totalEnergyUsage: Number,
  loadOptimizationData: [{
    timestamp: { type: Date, default: Date.now },
    weather: String,
    num_days: Number,
    time_resolution_minutes: Number,
    grid_connection: Number,
    solar_connection: Number,
    battery_capacity: Number,
    battery_voltage: Number,
    diesel_capacity: Number,
    fuel_price: Number,
    pv_energy_cost: Number,
    load_curtail_cost: Number,
    battery_om_cost: Number,
    profile_type: String,
    optimizationResults: {
      status: String,
      summary: {
        Weather: String,
        Days_Optimized: Number,
        Resolution_min: Number,
        Total_Load_kWh: Number,
        Solar_Used_kWh: Number,
        Grid_Used_kWh: Number,
        Total_Cost_INR: Number
      }
    }
  }],
});

const User = mongoose.model("User", userSchema);

module.exports = User;
