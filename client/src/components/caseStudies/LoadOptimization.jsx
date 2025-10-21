import { useContext, useState, useEffect } from "react";
import EnergyContext from "../../EnergyContext";
import axios from "axios";
import { Snackbar, Alert } from "@mui/material";

const LoadOptimization = () => {
  const { totalEnergyUsage, userEmail } = useContext(EnergyContext);
  const [formData, setFormData] = useState({
    weather: "Sunny",
    num_days: 2,
    time_resolution_minutes: 30,
    grid_connection: 2000,
    solar_connection: 2000,
    battery_capacity: 80000,  // Wh (matching notebook)
    battery_voltage: 100,
    diesel_capacity: 2200,
    fuel_price: 95,
    pv_energy_cost: 2.95,  // Matching notebook
    load_curtail_cost: 50,
    battery_om_cost: 0.085,  // Matching notebook
    profile_type: "Auto detect"
  });
  const [response, setResponse] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [open, setOpen] = useState(false);
  const [plotUrl, setPlotUrl] = useState(null);

  useEffect(() => {
    const savedResponse = localStorage.getItem("loadOptimizationResponse");
    if (savedResponse) {
      setResponse(JSON.parse(savedResponse));
    }
  }, []);

  const handleInputChange = (e) => {
    const { name, value, type } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: type === 'number' ? parseFloat(value) || 0 : value
    }));
  };

  const handleFileUpload = (e) => {
    const file = e.target.files[0];
    if (file) {
      setFormData(prev => ({
        ...prev,
        uploadedFile: file
      }));
    }
  };

  const handleSubmit = async () => {
    setLoading(true);
    setError(null);
    setOpen(false);

    try {
      // Create FormData for file upload
      const formDataToSend = new FormData();
      
      // Add file if uploaded
      if (formData.uploadedFile) {
        formDataToSend.append('file', formData.uploadedFile);
      }
      
      // Add all form parameters
      Object.keys(formData).forEach(key => {
        if (key !== 'uploadedFile') {
          formDataToSend.append(key, formData[key]);
        }
      });

      // Call the Python API
      const res = await axios.post(
        "http://localhost:8000/optimize",
        formDataToSend,
        {
          headers: {
            'Content-Type': 'multipart/form-data',
          },
        }
      );

      if (res.data.status === "success") {
        setResponse(res.data);
        const imageSrc = `data:image/png;base64,${res.data.plot_base64}`;
        setPlotUrl(imageSrc);
        localStorage.setItem("loadOptimizationResponse", JSON.stringify(res.data));
      } else {
        setError(res.data.message || "Optimization failed");
        setOpen(true);
      }

      // // Get the plot
      // const plotRes = await axios.post(
      //   "http://localhost:8000/optimize/plot",
      //   {
      //     weather: formData.weather,
      //     num_days: formData.num_days,
      //     time_resolution_minutes: formData.time_resolution_minutes
      //   },
      //   {
      //     responseType: 'blob'
      //   }
      // );

      // const plotBlob = new Blob([plotRes.data], { type: 'image/png' });
      // const plotUrl = URL.createObjectURL(plotBlob);
      // setPlotUrl(plotUrl);

      // Store response in localStorage
      localStorage.setItem(
        "loadOptimizationResponse",
        JSON.stringify(res.data)
      );

      if (res.data.status === "error") {
        setError(res.data.message || "Optimization failed");
        setOpen(true);
        return;
      }

      setResponse(res.data);

      // Save to MongoDB via Node.js server
      try {
        await axios.post("http://localhost:3000/save-load-optimization", {
          email: userEmail || "anonymous@example.com",
          ...formData,
          optimizationResults: res.data,
          timestamp: new Date().toISOString()
        });
      } catch (saveErr) {
        console.warn("Failed to save to database:", saveErr.message);
        // Don't show error to user for database save failure
      }

    } catch (err) {
      if (err.response?.data?.message) {
        setError(err.response.data.message);
      } else {
        setError(err.message || "An unexpected error occurred");
      }
      setOpen(true);
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    setOpen(false);
  };

  return (
    <div className="max-w-6xl mx-auto p-6 space-y-8">
      <div className="card bg-base-100 shadow-xl">
        <div className="card-body">
          <h2 className="card-title text-2xl font-bold mb-6 text-center">
            Load Optimization Analysis
          </h2>
          <p className="text-center mb-6 text-gray-600">
            Optimize your energy management system by analyzing load patterns, 
            solar generation, and grid interactions to minimize costs and maximize efficiency.
          </p>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Basic Parameters */}
            <div className="space-y-4">
              <h3 className="text-lg font-semibold">Basic Parameters</h3>
              
              <div className="form-control">
                <label className="label">
                  <span className="label-text">Weather Condition</span>
                </label>
                <select
                  name="weather"
                  value={formData.weather}
                  onChange={handleInputChange}
                  className="select select-bordered w-full"
                >
                  <option value="Sunny">Sunny</option>
                  <option value="Cloudy">Cloudy</option>
                  <option value="Rainy">Rainy</option>
                </select>
              </div>

              <div className="form-control">
                <label className="label">
                  <span className="label-text">Number of Days</span>
                </label>
                <input
                  type="number"
                  name="num_days"
                  value={formData.num_days}
                  onChange={handleInputChange}
                  className="input input-bordered w-full"
                  min="1"
                  max="30"
                />
              </div>

              <div className="form-control">
                <label className="label">
                  <span className="label-text">Time Resolution (minutes)</span>
                </label>
                <select
                  name="time_resolution_minutes"
                  value={formData.time_resolution_minutes}
                  onChange={handleInputChange}
                  className="select select-bordered w-full"
                >
                  <option value="15">15 minutes</option>
                  <option value="30">30 minutes</option>
                  <option value="60">60 minutes</option>
                </select>
              </div>

              <div className="form-control">
                <label className="label">
                  <span className="label-text">Profile Type</span>
                </label>
                <select
                  name="profile_type"
                  value={formData.profile_type}
                  onChange={handleInputChange}
                  className="select select-bordered w-full"
                >
                  <option value="Auto detect">Auto detect</option>
                  <option value="Residential">Residential</option>
                  <option value="Commercial">Commercial</option>
                  <option value="Industrial">Industrial</option>
                </select>
              </div>
            </div>

            {/* System Configuration */}
            <div className="space-y-4">
              <h3 className="text-lg font-semibold">System Configuration</h3>
              
              <div className="form-control">
                <label className="label">
                  <span className="label-text">Grid Connection (kW)</span>
                </label>
                <input
                  type="number"
                  name="grid_connection"
                  value={formData.grid_connection}
                  onChange={handleInputChange}
                  className="input input-bordered w-full"
                  step="100"
                />
              </div>

              <div className="form-control">
                <label className="label">
                  <span className="label-text">Solar Connection (kW)</span>
                </label>
                <input
                  type="number"
                  name="solar_connection"
                  value={formData.solar_connection}
                  onChange={handleInputChange}
                  className="input input-bordered w-full"
                  step="100"
                />
              </div>

              <div className="form-control">
                <label className="label">
                  <span className="label-text">Battery Capacity (Wh)</span>
                </label>
                <input
                  type="number"
                  name="battery_capacity"
                  value={formData.battery_capacity}
                  onChange={handleInputChange}
                  className="input input-bordered w-full"
                  step="1000"
                />
              </div>

              <div className="form-control">
                <label className="label">
                  <span className="label-text">Battery Voltage (V)</span>
                </label>
                <input
                  type="number"
                  name="battery_voltage"
                  value={formData.battery_voltage}
                  onChange={handleInputChange}
                  className="input input-bordered w-full"
                  step="10"
                />
              </div>
            </div>
          </div>

          {/* Cost Parameters */}
          <div className="mt-6">
            <h3 className="text-lg font-semibold mb-4">Cost Parameters</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="form-control">
                <label className="label">
                  <span className="label-text">Diesel Capacity (kW)</span>
                </label>
                <input
                  type="number"
                  name="diesel_capacity"
                  value={formData.diesel_capacity}
                  onChange={handleInputChange}
                  className="input input-bordered w-full"
                  step="100"
                />
              </div>

              <div className="form-control">
                <label className="label">
                  <span className="label-text">Fuel Price (Rs/L)</span>
                </label>
                <input
                  type="number"
                  name="fuel_price"
                  value={formData.fuel_price}
                  onChange={handleInputChange}
                  className="input input-bordered w-full"
                  step="0.1"
                />
              </div>

              <div className="form-control">
                <label className="label">
                  <span className="label-text">PV Energy Cost (Rs/kWh)</span>
                </label>
                <input
                  type="number"
                  name="pv_energy_cost"
                  value={formData.pv_energy_cost}
                  onChange={handleInputChange}
                  className="input input-bordered w-full"
                  step="0.01"
                />
              </div>

              <div className="form-control">
                <label className="label">
                  <span className="label-text">Load Curtail Cost (Rs/kWh)</span>
                </label>
                <input
                  type="number"
                  name="load_curtail_cost"
                  value={formData.load_curtail_cost}
                  onChange={handleInputChange}
                  className="input input-bordered w-full"
                  step="0.1"
                />
              </div>

              <div className="form-control">
                <label className="label">
                  <span className="label-text">Battery O&M Cost (Rs/kWh)</span>
                </label>
                <input
                  type="number"
                  name="battery_om_cost"
                  value={formData.battery_om_cost}
                  onChange={handleInputChange}
                  className="input input-bordered w-full"
                  step="0.001"
                />
              </div>
            </div>
          </div>

          {/* File Upload */}
          <div className="mt-6">
            <h3 className="text-lg font-semibold mb-4">Upload Custom Data (Optional)</h3>
            <div className="form-control">
              <label className="label">
                <span className="label-text">Upload CSV file with Load and Price data</span>
              </label>
              <input
                type="file"
                accept=".csv"
                onChange={handleFileUpload}
                className="file-input file-input-bordered w-full"
              />
              <label className="label">
                <span className="label-text-alt">CSV should have 'Load' and 'Price' columns</span>
              </label>
            </div>
          </div>

          <div className="flex justify-center mt-8">
            <button
              onClick={handleSubmit}
              className="btn bg-blue-600 text-white text-lg px-8 py-3"
              disabled={loading}
            >
              {loading ? "Optimizing..." : "Run Optimization"}
            </button>
          </div>
        </div>
      </div>

      {response && (
        <div className="space-y-8">
          {/* Optimization Summary */}
          <div className="card bg-base-100 shadow-xl">
            <div className="card-body">
              <h3 className="card-title text-xl font-semibold">
                Optimization Summary
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {Object.entries(response.summary).map(([key, value]) => {
                  const title = key.replace(/_/g, ' ');
                  const isObject = value && typeof value === 'object' && !Array.isArray(value);
                  return (
                    <div key={key} className="stat bg-base-200 rounded-lg p-4">
                      <div className="stat-title text-sm">{title}</div>
                      {!isObject ? (
                        <div className="stat-value text-lg">{String(value)}</div>
                      ) : (
                        <div className="space-y-1 mt-2">
                          {Object.entries(value).map(([k, v]) => (
                            <div key={k} className="text-sm flex justify-between">
                              <span className="text-gray-600">{k.replace(/_/g, ' ')}</span>
                              <span className="font-medium">{String(v)}</span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

          {/* Visualization */}
          {plotUrl && (
            <div className="card bg-base-100 shadow-xl">
              <div className="card-body">
                <h3 className="card-title text-xl font-semibold">
                  Load vs Solar Profile
                </h3>
                <div className="flex justify-center">
                  <img
                    src={plotUrl}
                    alt="Load vs Solar Profile"
                    className="max-w-full h-auto rounded-lg shadow-md"
                  />
                </div>
              </div>
            </div>
          )}

          {/* Key Insights */}
          <div className="card bg-base-100 shadow-xl">
            <div className="card-body">
              <h3 className="card-title text-xl font-semibold">
                Key Insights
              </h3>
              <div className="space-y-4">
                <div className="alert alert-info">
                  <div>
                    <h4 className="font-bold">Energy Distribution</h4>
                    <p>
                      Total load of {response.summary.Load?.Total_Demand_kWh} kWh was optimized with 
                      {response.summary.Solar?.Used_kWh} kWh from solar ({response.summary.Solar?.Used_Percent}% utilization) and 
                      {response.summary.Grid?.Import_kWh} kWh imported from grid.
                    </p>
                    {response.summary.Battery && (
                      <p className="mt-2">
                        Battery charged {response.summary.Battery?.Charged_kWh} kWh and discharged {response.summary.Battery?.Discharged_kWh} kWh.
                      </p>
                    )}
                  </div>
                </div>
                <div className="alert alert-success">
                  <div>
                    <h4 className="font-bold">Cost Analysis</h4>
                    <p>
                      Total optimized cost: ₹{response.summary.Costs?.TOTAL_COST_INR} for 
                      {response.summary.Optimization_Period_days} days with {response.summary.Resolution_min}-minute resolution.
                    </p>
                    <p className="mt-2">
                      Cost per kWh served: ₹{response.summary.Costs?.Cost_per_kWh_INR}
                    </p>
                  </div>
                </div>
                <div className="alert alert-warning">
                  <div>
                    <h4 className="font-bold">Weather Impact</h4>
                    <p>
                      Analysis performed under {response.summary.Weather} conditions, 
                      which significantly affects solar generation patterns.
                    </p>
                  </div>
                </div>
                {response.summary.Hydrogen && (
                  <div className="alert alert-accent">
                    <div>
                      <h4 className="font-bold">Hydrogen System</h4>
                      <p>
                        Electrolyzer consumed {response.summary.Hydrogen?.Electrolyzer_Energy_kWh} kWh and 
                        Fuel Cell generated {response.summary.Hydrogen?.Fuel_Cell_Energy_kWh} kWh.
                      </p>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      <Snackbar open={open} autoHideDuration={6000} onClose={handleClose}>
        <Alert onClose={handleClose} severity="error" sx={{ width: "100%" }}>
          {error}
        </Alert>
      </Snackbar>
    </div>
  );
};

export default LoadOptimization;
