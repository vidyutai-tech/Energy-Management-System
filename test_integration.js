#!/usr/bin/env node
/**
 * Integration Test Script for Source Optimization
 * This script tests the complete flow from frontend to backend to database
 */

const axios = require('axios');

const PYTHON_API_URL = 'http://localhost:8000';
const NODE_API_URL = 'http://localhost:3000';

async function testPythonAPI() {
  console.log('🧪 Testing Python API...');
  try {
    // Test health check
    const healthResponse = await axios.get(`${PYTHON_API_URL}/`);
    console.log('✅ Python API health check:', healthResponse.data.message);
    
    // Test optimization endpoint
    const optimizationData = {
      weather: 'Sunny',
      num_days: 2,
      time_resolution_minutes: 30,
      grid_connection: 2000,
      solar_connection: 2000,
      battery_capacity: 40000,
      battery_voltage: 100,
      diesel_capacity: 2200,
      fuel_price: 95,
      pv_energy_cost: 2.85,
      load_curtail_cost: 50,
      battery_om_cost: 6.085,
      profile_type: 'Auto detect'
    };
    
    const formData = new FormData();
    Object.keys(optimizationData).forEach(key => {
      formData.append(key, optimizationData[key]);
    });
    
    const optimizationResponse = await axios.post(`${PYTHON_API_URL}/optimize`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    
    console.log('✅ Python API optimization test:', optimizationResponse.data.status);
    return optimizationResponse.data;
  } catch (error) {
    console.error('❌ Python API test failed:', error.message);
    throw error;
  }
}

async function testNodeAPI() {
  console.log('🧪 Testing Node.js API...');
  try {
    // Test health check
    const healthResponse = await axios.get(`${NODE_API_URL}/`);
    console.log('✅ Node.js API health check:', healthResponse.data);
    
    // Test source optimization save endpoint
    const testData = {
      email: 'test@example.com',
      weather: 'Sunny',
      num_days: 2,
      time_resolution_minutes: 30,
      grid_connection: 2000,
      solar_connection: 2000,
      battery_capacity: 40000,
      battery_voltage: 100,
      diesel_capacity: 2200,
      fuel_price: 95,
      pv_energy_cost: 2.85,
      load_curtail_cost: 50,
      battery_om_cost: 6.085,
      profile_type: 'Auto detect',
      optimizationResults: {
        status: 'success',
        summary: {
          Weather: 'Sunny',
          Days_Optimized: 2,
          Resolution_min: 30,
          Total_Load_kWh: 1000,
          Solar_Used_kWh: 600,
          Grid_Used_kWh: 400,
          Total_Cost_INR: 2500
        }
      },
      timestamp: new Date().toISOString()
    };
    
    const saveResponse = await axios.post(`${NODE_API_URL}/save-load-optimization`, testData);
    console.log('✅ Node.js API save test:', saveResponse.data.message);
    
    // Test retrieval endpoint
    const historyResponse = await axios.get(`${NODE_API_URL}/load-optimization-history/test@example.com`);
    console.log('✅ Node.js API retrieval test:', historyResponse.data.message);
    console.log('📊 Saved optimizations:', historyResponse.data.data.length);
    
  } catch (error) {
    console.error('❌ Node.js API test failed:', error.message);
    throw error;
  }
}

async function runIntegrationTest() {
  console.log('🚀 Starting Source Optimization Integration Test');
  console.log('=' .repeat(50));
  
  try {
    await testPythonAPI();
    console.log('');
    await testNodeAPI();
    console.log('');
    console.log('🎉 All tests passed! Integration is working correctly.');
    console.log('');
    console.log('📋 Next steps:');
    console.log('1. Start the React frontend: cd client && npm run dev');
    console.log('2. Navigate to Case Studies > Source Optimization');
    console.log('3. Configure parameters and run optimization');
    console.log('4. Check MongoDB for saved data');
    
  } catch (error) {
    console.error('');
    console.error('💥 Integration test failed!');
    console.error('Please check:');
    console.error('1. Python API is running on port 8000');
    console.error('2. Node.js API is running on port 3000');
    console.error('3. MongoDB is connected');
    console.error('4. All dependencies are installed');
    process.exit(1);
  }
}

// Run the test
runIntegrationTest();
