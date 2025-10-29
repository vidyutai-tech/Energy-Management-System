const express = require("express");
const mongoose = require("mongoose");
const cors = require("cors");
const User = require("./models/user");
const dotenv = require("dotenv");

dotenv.config();

const app = express();
const mongoURL = process.env.DB_URL;

// Connect to MongoDB
mongoose
  .connect(mongoURL)
  .then(() => {
    console.log("Connected to MongoDB");
  })
  .catch((err) => {
    console.error("Failed to connect to MongoDB", err);
  });

app.use(cors());
app.use(express.json());

app.get("/", (req, res) => {
  res.send("Backend says hi!!");
});

// POST route to handle form submission
app.post("/submit", async (req, res) => {
  try {
    const { name, email, appliances, misc, choices, totalEnergyUsage } =
      req.body;

    const existingUser = await User.findOne({ email });

    if (existingUser) {
      // Update the existing user with the new values
      existingUser.name = name;
      existingUser.appliances = appliances;
      existingUser.misc = misc;
      existingUser.choices = choices;
      existingUser.totalEnergyUsage = totalEnergyUsage;

      await existingUser.save();
      res.status(200).json({ message: "User data updated successfully!" });
    } else {
      // Create a new user
      const newUser = new User({
        name,
        email,
        appliances,
        misc,
        choices,
        totalEnergyUsage,
      });

      await newUser.save();
      res
        .status(201)
        .json({ message: "New user created and data submitted successfully!" });
    }
  } catch (error) {
    console.error("Error saving data", error);
    res.status(500).json({ message: "Failed to submit data" });
  }
});

// POST route to handle source optimization data
app.post("/save-load-optimization", async (req, res) => {
  try {
    const { 
      email = "anonymous@example.com", // Default email if not provided
      weather,
      num_days,
      time_resolution_minutes,
      grid_connection,
      solar_connection,
      battery_capacity,
      battery_voltage,
      diesel_capacity,
      fuel_price,
      pv_energy_cost,
      load_curtail_cost,
      battery_om_cost,
      profile_type,
      optimizationResults,
      timestamp
    } = req.body;

    // Find existing user or create a new one
    let user = await User.findOne({ email });
    
    if (!user) {
      // Create a new user with minimal data
      user = new User({
        name: "Anonymous User",
        email,
        appliances: new Map(),
        misc: [],
        choices: {
          energySource: [],
          dieselUse: "",
          energyGoal: ""
        },
        totalEnergyUsage: 0,
        loadOptimizationData: []
      });
    }

    // Add the source optimization data
    const optimizationData = {
      timestamp: timestamp ? new Date(timestamp) : new Date(),
      weather,
      num_days,
      time_resolution_minutes,
      grid_connection,
      solar_connection,
      battery_capacity,
      battery_voltage,
      diesel_capacity,
      fuel_price,
      pv_energy_cost,
      load_curtail_cost,
      battery_om_cost,
      profile_type,
      optimizationResults
    };

    user.loadOptimizationData.push(optimizationData);
    await user.save();

    res.status(200).json({ 
      message: "Source optimization data saved successfully!",
      dataId: optimizationData.timestamp
    });
  } catch (error) {
    console.error("Error saving source optimization data", error);
    res.status(500).json({ message: "Failed to save source optimization data" });
  }
});

// GET route to retrieve source optimization history for a user
app.get("/load-optimization-history/:email", async (req, res) => {
  try {
    const { email } = req.params;
    const user = await User.findOne({ email });
    
    if (!user) {
      return res.status(404).json({ message: "User not found" });
    }

    res.status(200).json({
      message: "Source optimization history retrieved successfully",
      data: user.loadOptimizationData || []
    });
  } catch (error) {
    console.error("Error retrieving source optimization history", error);
    res.status(500).json({ message: "Failed to retrieve source optimization history" });
  }
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});
