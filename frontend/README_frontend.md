# 3D digital-twin frontend

React 18 + TypeScript + Vite + three.js + React Three Fiber + drei + Tailwind + Recharts + @react-three/xr.

```bash
npm install
VITE_BACKEND_HTTP=http://localhost:8000 npm run dev     # backend must be running (backend/README_twin_backend.md)
```

## Every animation reads backend state

| Visual | Driven by (WebSocket field) | Where |
|---|---|---|
| GPU node colour / glow | `simulated.twin_temperature`, banded around the backend's `threshold_C` (−15 / −5 / 0 / +5 °C) | `src/racks/Racks.tsx` |
| Node status-LED blink rate | `measured.gpu_utilization` | `src/racks/Racks.tsx` |
| Amber outline on a node | active `thermal_event_predicted` for that GPU | `src/racks/Racks.tsx` |
| Coolant particle speed | rack Σ `simulated.coolant_flow_lpm` ÷ GPUs × 0.55 units/s per L/min | `src/cooling/CoolingLoop.tsx` |
| Return-pipe particle whitening | Σ `simulated.vapour_generation_g_s` | `src/cooling/CoolingLoop.tsx` |
| Valve handle angle and "VALVE n %" | mean `simulated.valve_position` × 90° | `src/cooling/CoolingLoop.tsx` |
| Pump impeller speed | `cdu.total_flow_lpm` | `src/cooling/CoolingLoop.tsx` |
| GPU close-up die / cold plate colour, channel particles | `twin_temperature`, `cold_plate_temperature`, `coolant_flow_lpm` | `src/gpu/GpuDetail.tsx` |
| Forecast hologram + 3D forecast path | `predicted.*` (source shown: ML or persistence) | `src/prediction/Prediction.tsx` |
| Camera event sequence | starts on `thermal_event_predicted`. Each step advances when the data show the change (valve command issued → valve reached command → temperature trend ≤ 0.02 °C/s), with time caps | `src/scene/CameraDirector.tsx` |
| Control-room screens, results page | frames and `/api/results` files | `src/control-room/`, `src/components/ResultsPage.tsx` |

Values are smoothed toward the latest backend value (exponential damping). The frontend never makes up a target value.
Fields that are null in the data (e.g. clocks in most traces) are hidden.

Notes
- drei `<Text>` loads its font from the jsDelivr CDN at runtime. Labels have their own Suspense boundaries,
  so the scene still renders if the CDN is slow or blocked.
- ENTER VR appears only when `navigator.xr` reports `immersive-vr` support.
- The previous prototype `src/` is preserved in `../legacy/frontend_src_prototype/`.
