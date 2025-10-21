
---

## 🧠 **Energy Management System (EMS)**

A full-stack hybrid energy optimization platform that allows users to **upload load profiles**, adjust energy parameters, and run an **optimization model** (using MILP in FastAPI) to minimize total energy cost.

The UI provides file upload, parameter control, and result visualization — all connected to the Python optimization engine.

---

### 📁 **Project Structure**

```
Energy-MANAGEMENT-SYSTEM/
│
├── client/                     # React + Vite frontend
│   ├── src/
│   │   ├── components/
│   │   │   └── UploadOptimizer.jsx
│   │   └── App.jsx
│   ├── package.json
│   ├── vite.config.js
│   └── .env                    # Frontend environment variables
│
├── python_backend/             # FastAPI backend
│   └── ems_api.py              # Single-file backend API
│
├── notebooks/                  # Optional Jupyter notebook reference
│   └── website_EMS_improved.ipynb
│
├── venv/                       # Python virtual environment
│
└── requirements.txt
```

---

## ⚙️ **Setup Instructions**

### 🐍 Backend (FastAPI)

1. **Create and activate a virtual environment**

   ```bash
   python -m venv venv
   source venv/Scripts/activate      # (Windows)
   # or
   source venv/bin/activate          # (Mac/Linux)
   ```

2. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

   *(If `requirements.txt` not ready, create with:)*

   ```bash
   pip install fastapi uvicorn pulp matplotlib numpy pandas
   pip freeze > requirements.txt
   ```

3. **Run FastAPI server**

   ```bash
   cd python_backend
   uvicorn ems_api:app --reload --port 8000
   ```

   ✅ API will be available at → [http://127.0.0.1:8000](http://127.0.0.1:8000)
   ✅ Swagger docs → [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

### ⚛️ Frontend (React + Vite)

1. **Move into frontend**

   ```bash
   cd client
   ```

2. **Install packages**

   ```bash
   npm install
   ```

3. **Create `.env` file**

   ```bash
   VITE_API_URL=http://127.0.0.1:8000
   ```

4. **Run frontend**

   ```bash
   npm run dev
   ```

   ✅ App runs at → [http://localhost:5173](http://localhost:5173)

---

## 🔄 **Connecting Frontend ↔ Backend**

Your React frontend sends requests to FastAPI using `fetch()`:

```js
const response = await fetch(`${import.meta.env.VITE_API_URL}/optimize`, {
  method: "POST",
  body: formData,
});
```

The FastAPI backend:

* Accepts file + parameters
* Runs optimization logic
* Returns cost summary and performance metrics as JSON

---

## 🧮 **Core Backend Features**

* **Upload CSV** (with columns `Load`, `Price`)
* **Custom parameters** (grid, solar, battery, diesel)
* **Piecewise linear MILP optimization** using `pulp`
* **Weather-based solar profile selection (Sunny/Rainy)**
* **Output:** Total cost, solar/grid usage, round-trip efficiency
* **Visualization:** Optional PNG plot returned from `/optimize/plot`

---

## 💡 **Endpoints Overview**

| Endpoint         | Method | Description                                      |
| ---------------- | ------ | ------------------------------------------------ |
| `/`              | GET    | Health check                                     |
| `/optimize`      | POST   | Run optimization with uploaded file & parameters |
| `/optimize/plot` | POST   | Generate and return power dispatch plot          |

---

## 🧩 **Example cURL Request**

```bash
curl -X POST "http://127.0.0.1:8000/optimize" \
  -F "weather=Sunny" \
  -F "num_days=2" \
  -F "grid_connection=2000" \
  -F "solar_connection=2000" \
  -F "battery_capacity=40000" \
  -F "file=@sample_load.csv"
```

---

## 📊 **Typical Output (JSON)**

```json
{
  "status": "success",
  "summary": {
    "Weather": "Sunny",
    "Days_Optimized": 2,
    "Resolution_min": 30,
    "Total_Load_kWh": 65850.0,
    "Solar_Used_kWh": 52400.0,
    "Grid_Used_kWh": 13450.0,
    "Total_Cost_INR": 196235.5
  }
}
```

---

## 🎨 **Frontend Features**

* Intuitive upload form
* Parameter fields (grid, solar, diesel, battery, etc.)
* “Upload & Optimize” button triggers backend computation
* Results shown dynamically on-screen
* Optional chart visualization for solar/load dispatch

---

## 🧱 **Tech Stack**

| Layer         | Technology                       |
| ------------- | -------------------------------- |
| Frontend      | React + Vite + TailwindCSS       |
| Backend       | FastAPI (Python 3.9+)            |
| Optimization  | PuLP (MILP Solver)               |
| Visualization | Matplotlib                       |
| Data          | CSV Uploads / Synthetic profiles |

