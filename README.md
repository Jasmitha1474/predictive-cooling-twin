# Predictive Thermal Control for Two-Phase Direct-to-Chip GPU Cooling

> **Digital Twin Simulation** — An immersive 3D visualization of AI-driven predictive thermal management for GPU data centers.

![Status](https://img.shields.io/badge/Status-Prototype-blue)
![License](https://img.shields.io/badge/License-MIT-green)

> [!NOTE]
> This is a **simulation / digital-twin project**. There is no physical cooling hardware. The system simulates an AI-dense GPU server, two-phase direct-to-chip cooling, thermal behavior, ML prediction, and predictive control using realistic real-time synthetic telemetry.

## 🎯 Project Objective

Demonstrate how machine learning can **predict GPU junction temperature 30–60 seconds ahead** and proactively adjust cooling before a thermal spike occurs, compared to conventional reactive threshold-based cooling.

## 🏗 Architecture

```
                  REMOTE CLOUD (Google Colab)
        ┌─────────────────────────────────┐
        │ Synthetic Telemetry Dataset     │
        │ LightGBM Model Training         │
        │ Model Evaluation & Metrics      │
        └──────────────┬──────────────────┘
                       │ trained model (.joblib)
                       ▼
              ┌─────────────────────┐
              │ Cloud Backend       │
              │ FastAPI + WebSocket │
              │ Thermal Simulator   │
              │ ML Inference        │
              │ Controllers         │
              └────────┬────────────┘
                       │ real-time telemetry
                       ▼
              ┌─────────────────────┐
              │ React Frontend      │
              │ 3D Digital Twin     │
              │ React Three Fiber   │
              │ Real-time Charts    │
              └─────────────────────┘
```

## 🔬 System Workflow

```
GPU Workload → Telemetry → Feature Engineering → ML Thermal Forecast
    → Predictive Controller → Coolant/Valve Command
    → Simulated Cooling Response → New Temperature → Feedback → Next Prediction
```

## 🧠 ML Methodology

### Model
- **Primary**: LightGBM (Gradient Boosting) — lightweight, fast CPU inference
- **Alternative**: LSTM (provided as training notebook option)
- **Export format**: `.joblib` (scikit-learn compatible)

### Features
| Feature | Description |
|---|---|
| `gpu_utilization` | Current GPU utilization % |
| `gpu_power` | Current GPU power draw (W) |
| `gpu_memory` | GPU memory utilization % |
| `gpu_clock` | GPU clock frequency (MHz) |
| `gpu_temperature` | Current junction temperature (°C) |
| `coolant_temperature` | Coolant temperature (°C) |
| `coolant_flow_rate` | Coolant flow rate (L/min) |
| `valve_position` | Valve position (%) |
| `power_rolling_mean_10` | 10-step rolling mean of power |
| `power_rolling_max_10` | 10-step rolling max of power |
| `temperature_slope_5` | 5-step temperature slope |
| `power_slope_5` | 5-step power slope |
| `workload_encoded` | One-hot encoded workload type |

### Prediction Targets
- `future_temperature_30s` — GPU junction temperature 30 seconds ahead
- `future_power_30s` — GPU power draw 30 seconds ahead

### Metrics
All metrics are computed from actual training/evaluation, not fabricated:
- **MAE** (Mean Absolute Error)
- **RMSE** (Root Mean Squared Error)
- **R²** (Coefficient of Determination)
- **Inference Latency** (ms)

## 🌡 Dataset Strategy

### Mode A: Synthetic Simulation Data (Default)
A scientifically reasonable synthetic dataset is generated containing realistic relationships between workload, utilization, power, memory, clock, and temperature. Includes workload transitions and burst events.

> **Clearly labeled as SYNTHETIC DATA** — not from physical hardware.

### Mode B: Real/Remote Data
The architecture supports swapping in real GPU telemetry data (e.g., NVIDIA DCGM logs) without code changes. Train remotely, export only the model artifact.

## 🌀 Thermal Simulation

Simplified lumped-parameter thermal model:

```
T_gpu(t+Δt) = T_gpu(t) + (Δt / C_th) × [P_gpu(t) - Q_cool(t)]

Q_cool = ṁ × c_p × (T_gpu - T_coolant) × η_valve
```

**Parameters:**
| Parameter | Value | Description |
|---|---|---|
| C_thermal | 50 J/°C | GPU + heatsink thermal mass |
| T_ambient | 25 °C | Ambient temperature |
| T_coolant_supply | 30 °C | Coolant supply temperature |
| Max cooling | 1200 W | Max cooling at full flow |

> [!IMPORTANT]
> This is a **simplified thermal model**, not a full fluid dynamics simulation of two-phase boiling. It captures the essential thermal behavior for demonstrating predictive control.

## 🎮 Controller Methodology

### Reactive Controller (Baseline)
```
IF current_temperature > threshold:
    increase coolant flow proportionally
ELSE:
    maintain baseline cooling
```

### Predictive Controller (ML-Based)
```
predicted_temps = model.predict(features)
IF predicted_temp approaching threshold:
    gradually increase cooling
IF predicted_temp spike expected:
    aggressively increase cooling NOW
IF predicted_temp stable:
    reduce toward efficient setpoint
```

## 🖥 Frontend Architecture

- **React 18** + **TypeScript** + **Vite**
- **React Three Fiber** + **@react-three/drei** for 3D rendering
- **Zustand** for state management
- **Recharts** for 2D analytics charts
- **Tailwind CSS** for UI styling
- **WebSocket** for real-time telemetry streaming

### 3D Digital Twin Features
- Immersive data center room with server racks
- GPU nodes with temperature-driven color states
- Animated coolant particles flowing through pipes (speed = flow rate)
- Mechanical valve animation (rotation = valve position)
- Cooling Distribution Unit with animated pump
- Holographic floating data panels
- 3D prediction path visualization
- Thermal overlay mode
- 6 preset camera views with smooth transitions
- WebXR-ready architecture

## ⚙ Backend Architecture

- **FastAPI** with WebSocket support
- **Async simulation loop** at 10Hz physics / 1Hz broadcast
- **ML inference** with joblib model loading
- **CORS** enabled for cross-origin frontend
- **REST API** for simulation control
- **WebSocket** for continuous telemetry streaming

## 🚀 How to Run

### Prerequisites
- Python 3.10+
- Node.js 18+
- npm or yarn

### Backend
```bash
cd backend
pip install -r requirements.txt

# Train bootstrap model (first time only)
python -m ml.bootstrap_model

# Start server
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 in your browser.

### Remote Training (Google Colab)
1. Open `training/01_dataset_generation.ipynb` in Google Colab
2. Run all cells to generate synthetic dataset
3. Open `training/02_model_training.ipynb` and run training
4. Open `training/03_model_evaluation.ipynb` for evaluation
5. Download the trained model artifact
6. Place in `backend/models/thermal_model.joblib`

## 🌐 Deployment

### Frontend → Vercel / Netlify
```bash
cd frontend
npm run build
# Deploy dist/ folder
```

### Backend → Render / Railway
```bash
# Use the provided Dockerfile or:
uvicorn main:app --host 0.0.0.0 --port $PORT
```

### Connecting Frontend to Backend
Set the `VITE_WS_URL` environment variable:
```bash
VITE_WS_URL=wss://your-backend.onrender.com
```

## ⚠ Limitations

1. **Thermal model is simplified** — does not simulate full two-phase boiling fluid dynamics
2. **Synthetic data** — model accuracy metrics are from synthetic data, not real hardware
3. **Energy estimates are relative** — pump energy model is simplified, not based on actual commercial pump specifications
4. **Single-server simulation** — demonstrates the concept; real data centers have complex interdependencies
5. **No real GPU telemetry** — all telemetry is simulated; accuracy claims apply only to the synthetic domain

## 🔮 Future Work

- Integration with real NVIDIA DCGM telemetry
- LSTM/Transformer model variants
- Multi-zone cooling optimization
- Physical pump energy modeling
- Full WebXR VR walkthrough mode
- Multi-user collaborative monitoring
- Historical replay and analysis
- Edge deployment with ONNX Runtime

## 📄 License

MIT License
