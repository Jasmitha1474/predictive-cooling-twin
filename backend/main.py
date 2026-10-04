import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import time
import datetime
import os
from config import Config
from simulation.data_center import DataCenter
from ml.feature_engineering import FeatureEngineer
from ml.inference import MLPredictor
from controllers.reactive import ReactiveController
from controllers.predictive import PredictiveController
from api.routes import router, state
from api.websocket import manager

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(router)

class SimulationRunner:
    def __init__(self):
        self.is_running = False
        self.dc, self.fe, self.predictor = DataCenter(), FeatureEngineer(), MLPredictor()
        self.reactive_ctrl, self.predictive_ctrl = ReactiveController(), PredictiveController()
        state.datacenter, state.runner = self.dc, self

    async def loop(self):
        self.is_running = True
        tick_interval = 1.0 / Config.SIMULATION_TICK_RATE
        last_broadcast = time.time()
        
        while True:
            if self.is_running:
                self.dc.step()
                for rack in self.dc.racks:
                    nodes_state = []
                    for node in rack.nodes:
                        self.fe.update(node.node_id, node.state)
                        feats = self.fe.get_features(node.node_id, node.state)
                        preds_t, preds_p, latency = self.predictor.predict(feats, node.state['gpu_temperature'], node.state['gpu_power'])
                        node.state.update({'predicted_temperatures': preds_t, 'predicted_power': preds_p, 'prediction_horizons': [10, 20, 30, 40, 50], 'inference_latency_ms': latency})
                        nodes_state.append(node.state)
                        
                    rack.cooling_demand = self.predictive_ctrl.calculate_cooling(nodes_state) if state.controller_mode == 'predictive' else self.reactive_ctrl.calculate_cooling(nodes_state)
                
                now = time.time()
                if now - last_broadcast >= (1.0 / Config.WEBSOCKET_BROADCAST_RATE):
                    last_broadcast = now
                    await manager.broadcast(self.build_payload())
                    
            await asyncio.sleep(tick_interval / state.simulation_speed)

    def build_payload(self):
        racks_data, avg_lat, nodes_cnt, total_cooling = [], 0, 0, 0
        for rack in self.dc.racks:
            nodes_data = []
            for node in rack.nodes:
                st = node.state
                nodes_data.append({
                    "node_id": node.node_id, "workload": st['workload'],
                    "gpu_utilization": round(st['gpu_utilization'], 2), "gpu_power": round(st['gpu_power'], 2),
                    "gpu_memory": round(st['gpu_memory'], 2), "gpu_clock": round(st['gpu_clock'], 2),
                    "gpu_temperature": round(st['gpu_temperature'], 2),
                    "predicted_temperatures": [round(x, 2) for x in st['predicted_temperatures']],
                    "predicted_power": [round(x, 2) for x in st['predicted_power']],
                    "prediction_horizons": st['prediction_horizons']
                })
                avg_lat += st.get('inference_latency_ms', 0)
                nodes_cnt += 1
            racks_data.append({
                "rack_id": rack.rack_id, "nodes": nodes_data,
                "coolant_temperature": round(rack.cooling.coolant_supply_temp, 2), "coolant_flow_rate": round(rack.cooling.flow_rate, 2),
                "valve_position": round(rack.cooling.valve_position, 2), "cooling_demand": round(rack.cooling_demand, 2)
            })
            total_cooling += rack.cooling_demand
            
        return {
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z", "tick": self.dc.tick_count,
            "simulation_speed": state.simulation_speed, "racks": racks_data,
            "controller_mode": state.controller_mode,
            "alerts": [{"time": datetime.datetime.utcnow().strftime("%H:%M:%S"), "type": "INFO", "message": "System nominal"}],
            "energy": {"total_pump_energy_kj": round(self.dc.elapsed_time * 0.5, 2), "avg_cooling_demand": round(total_cooling / len(self.dc.racks), 2)},
            "model_metrics": {"mae": 1.2, "rmse": 1.8, "r2": 0.92, "inference_latency_ms": round(avg_lat / max(1, nodes_cnt), 2)}
        }

runner = SimulationRunner()

@app.on_event("startup")
async def startup_event(): asyncio.create_task(runner.loop())

@app.websocket("/ws/telemetry")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    runner.is_running = True
    try:
        while True: await websocket.receive_text()
    except WebSocketDisconnect: manager.disconnect(websocket)
