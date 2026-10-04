from fastapi import APIRouter
from pydantic import BaseModel
import os

router = APIRouter()

class GlobalState:
    datacenter = None
    runner = None
    simulation_speed = 1.0
    controller_mode = 'predictive'

state = GlobalState()

@router.get('/api/status')
def get_status(): return {"status": "running" if state.runner and state.runner.is_running else "stopped"}

@router.get('/api/model')
def get_model():
    if os.path.exists('models/model_metadata.json'):
        with open('models/model_metadata.json', 'r') as f: return f.read()
    return {"error": "no model"}

@router.get('/api/metrics')
def get_metrics(): return {"metrics": "ok"}

class WorkloadReq(BaseModel):
    type: str
    rack_id: str = None
    node_id: str = None

@router.post('/api/workload')
def set_workload(req: WorkloadReq):
    if not state.datacenter: return {"error": "no datacenter"}
    for r in state.datacenter.racks:
        if not req.rack_id or r.rack_id == req.rack_id:
            for n in r.nodes:
                if not req.node_id or n.node_id == req.node_id: n.workload.profile_type = req.type
    return {"status": "ok"}

class ControllerReq(BaseModel): mode: str

@router.post('/api/controller')
def set_controller(req: ControllerReq):
    state.controller_mode = req.mode
    return {"status": "ok"}

class SpeedReq(BaseModel): speed: float

@router.post('/api/simulation/speed')
def set_speed(req: SpeedReq):
    state.simulation_speed = req.speed
    return {"status": "ok"}

@router.post('/api/simulation/start')
def start_sim():
    if state.runner: state.runner.is_running = True
    return {"status": "started"}

@router.post('/api/simulation/stop')
def stop_sim():
    if state.runner: state.runner.is_running = False
    return {"status": "stopped"}

@router.post('/api/simulation/reset')
def reset_sim(): return {"status": "reset"}

@router.post('/api/simulation/settings')
def set_settings(settings: dict): return {"status": "ok"}
