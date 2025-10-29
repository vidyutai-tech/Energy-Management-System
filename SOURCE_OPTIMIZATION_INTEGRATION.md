# Source Optimization Integration Guide

This document explains how to run the integrated Energy Management System with the new Source Optimization feature.

## Overview

The Source Optimization feature has been successfully integrated into the Energy Management System. It includes:

- A new "Source Optimization" tab in the Case Studies section
- Python FastAPI backend for optimization calculations
- MongoDB integration for data persistence
- React frontend with comprehensive form and results display

## Architecture

```
Frontend (React) → Node.js Server → MongoDB
       ↓
Python FastAPI (Source Optimization)
```

## Setup Instructions

### 1. Python Backend Setup

Navigate to the python-backend directory and install dependencies:

```bash
cd python-backend
pip install -r ../requirements.txt
```

Start the Python API server:

```bash
python start_api.py
```

The API will be available at `http://localhost:8000`

### 2. Node.js Backend Setup

Navigate to the server directory and install dependencies:

```bash
cd server
npm install
```

Set up your MongoDB connection by creating a `.env` file:

```env
DB_URL=your_mongodb_connection_string
PORT=3000
```

Start the Node.js server:

```bash
npm run dev
```

The server will be available at `http://localhost:3000`

### 3. React Frontend Setup

Navigate to the client directory and install dependencies:

```bash
cd client
npm install
```

Start the development server:

```bash
npm run dev
```

The frontend will be available at `http://localhost:5173`

## Features

### Source Optimization Tab

The new Source Optimization tab provides:

1. **Parameter Configuration**:
   - Weather conditions (Sunny/Rainy)
   - Number of days to optimize
   - Time resolution (15/30/60 minutes)
   - System configuration (grid, solar, battery parameters)
   - Cost parameters (fuel, PV energy, maintenance costs)

2. **Data Input**:
   - Default load and price profiles
   - Optional CSV file upload for custom data
   - Real-time parameter adjustment

3. **Optimization Results**:
   - Summary statistics (total load, solar usage, grid usage, costs)
   - Visual charts showing load vs solar profiles
   - Key insights and recommendations

4. **Data Persistence**:
   - All optimization runs are saved to MongoDB
   - User-specific optimization history
   - Timestamp tracking for analysis

## API Endpoints

### Python FastAPI Endpoints

- `POST /optimize` - Run source optimization with parameters
- `POST /optimize/plot` - Generate visualization plots
- `GET /` - Health check

### Node.js API Endpoints

- `POST /save-load-optimization` - Save optimization data to MongoDB
- `GET /load-optimization-history/:email` - Retrieve user's optimization history
- `POST /submit` - Original form submission (unchanged)

## Database Schema

The MongoDB schema has been extended to include source optimization data:

```javascript
loadOptimizationData: [{
  timestamp: Date,
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
}]
```

## Usage

1. Start all three servers (Python API, Node.js, React)
2. Navigate to the Case Studies section
3. Click on the "Source Optimization" tab
4. Configure your parameters or upload custom data
5. Click "Run Optimization"
6. View results and insights
7. Data is automatically saved to MongoDB

## Troubleshooting

### Common Issues

1. **CORS Errors**: Ensure the Python API is running on port 8000
2. **MongoDB Connection**: Check your DB_URL in the .env file
3. **Port Conflicts**: Make sure ports 3000, 5173, and 8000 are available
4. **Python Dependencies**: Install all requirements from requirements.txt

### Logs

- Python API: Check console output for optimization logs
- Node.js: Check console for database connection and API logs
- React: Check browser console for frontend errors

## Future Enhancements

- Historical data visualization
- Comparison between different optimization runs
- Export functionality for results
- Advanced optimization algorithms
- Real-time monitoring dashboard

## Support

For issues or questions regarding the Source Optimization integration, please check the console logs and ensure all services are running properly.
