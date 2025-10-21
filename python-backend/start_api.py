#!/usr/bin/env python3
"""
Startup script for the Energy Management System API
"""
import uvicorn
import os
import sys

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    print("🚀 Starting Energy Management System API...")
    print("📍 API will be available at: http://localhost:8000")
    print("📚 API documentation at: http://localhost:8000/docs")
    print("🛑 Press Ctrl+C to stop the server")
    print("-" * 50)
    
    uvicorn.run(
        "ems_api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
