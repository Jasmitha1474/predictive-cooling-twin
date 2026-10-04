"""FastAPI app: REST + /ws/telemetry. Run from backend/:  uvicorn app.main:app --port 8000

Environment variables:
  PCOOL_REPLAY_PACK  path to replay_pack.parquet (default backend/data/replay_pack.parquet)
  PCOOL_MODEL        'lgbm:<dir with d_power_30.txt...>' or 'lstm:<model.pt>'; unset = no ML model
  PCOOL_REPORTS      directory with results.json, audit_summary.json, split_report.json, e2_results*.json
  PCOOL_RACKS / PCOOL_GPUS_PER_RACK   virtual layout (default 4 x 5)

With no model, predictions come from persistence and every frame says so
(model_status = "NOT_LOADED", forecast_source = "persistence_baseline_not_ml").
"""
from __future__ import annotations

import asyncio
import json
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.engine import Engine
from app.replay import ReplayPack
from controller.forecasters import PersistenceForecaster, load_forecaster
from simulation.twin import TwinParams

BACKEND = Path(__file__).resolve().parents[1]
REPORTS = Path(os.environ.get("PCOOL_REPORTS", BACKEND.parent / "research" / "reports"))


def load_model() -> tuple[object, dict]:
    spec = os.environ.get("PCOOL_MODEL", "").strip()
    if not spec:
        return PersistenceForecaster(), dict(state="NOT_LOADED", forecast_source="persistence_baseline_not_ml",
                                             detail="No exported model configured (PCOOL_MODEL unset).")
    kind, _, path = spec.partition(":")
    model_path = Path(path)
    manifest_path = (model_path.parent if kind == "lgbm" else model_path.parent.parent) / "manifest.json"
    if not manifest_path.exists():
        # refuse models without provenance (docs/methodology.md section 9)
        return PersistenceForecaster(), dict(state="REJECTED_NO_MANIFEST", forecast_source="persistence_baseline_not_ml",
                                             detail=f"{manifest_path} not found; model not loaded.")
    try:
        f = load_forecaster(spec)
    except Exception as e:  # report the failure instead of hiding it
        return PersistenceForecaster(), dict(state="LOAD_FAILED", forecast_source="persistence_baseline_not_ml",
                                             detail=repr(e))
    m = json.loads(manifest_path.read_text())
    return f, dict(state="ACTIVE", forecast_source="ml_model", model_id=f.name, spec=spec,
                   manifest=dict(dataset=m.get("dataset"), config_hash=m.get("config_hash"),
                                 created_utc=m.get("created_utc"), code_commit=m.get("code_commit")))


@asynccontextmanager
async def lifespan(app: FastAPI):
    pack_path = Path(os.environ.get("PCOOL_REPLAY_PACK", BACKEND / "data" / "replay_pack.parquet"))
    if not pack_path.exists():   # deployments: build from the public dataset at startup
        from app.replay import build_from_s3
        pack_path = build_from_s3(BACKEND / "replay_jobs.json", Path(os.environ.get("PCOOL_CACHE", "/tmp/pcool")) / "replay_pack.parquet")
    pack = ReplayPack(pack_path)
    forecaster, status = load_model()
    params = None
    for name in ("e2_results.json", "e2_results_preliminary.json"):   # use the calibrated twin of the experiment
        f = REPORTS / name
        if f.exists():
            params = TwinParams(**json.loads(f.read_text())["twin_params"])
            break
    app.state.engine = Engine(pack, forecaster, status, racks=int(os.environ.get("PCOOL_RACKS", 4)),
                              per_rack=int(os.environ.get("PCOOL_GPUS_PER_RACK", 5)), params=params)
    app.state.clients = set()
    task = asyncio.create_task(_loop(app))
    yield
    task.cancel()


async def _loop(app: FastAPI):
    eng: Engine = app.state.engine
    while True:
        if not eng.paused and app.state.clients:
            frame = eng.step()
            msg = json.dumps(frame)
            dead = []
            for ws in list(app.state.clients):
                try:
                    await ws.send_text(msg)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                app.state.clients.discard(ws)
        await asyncio.sleep(1.0 / eng.speed)


app = FastAPI(title="Predictive cooling digital twin", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=os.environ.get("PCOOL_CORS", "*").split(","),
                   allow_methods=["*"], allow_headers=["*"])


@app.websocket("/ws/telemetry")
async def ws_telemetry(ws: WebSocket):
    await ws.accept()
    await ws.send_text(json.dumps(app.state.engine.describe()))
    app.state.clients.add(ws)
    try:
        while True:  # clients may also send control messages over the socket
            msg = json.loads(await ws.receive_text())
            if msg.get("type") == "control":
                app.state.engine.configure(**{k: msg[k] for k in ("mode", "controller_mode", "paused", "speed", "reset")
                                              if k in msg})
                await ws.send_text(json.dumps(dict(type="control_ack", **_status())))
    except WebSocketDisconnect:
        pass
    finally:
        app.state.clients.discard(ws)


class Control(BaseModel):
    mode: str | None = None
    controller_mode: str | None = None
    paused: bool | None = None
    speed: float | None = None
    reset: bool = False


class Assign(BaseModel):
    gpu_id: str
    series_id: str


def _status():
    e: Engine = app.state.engine
    return dict(mode=e.mode, controller_mode=e.controller_mode, paused=e.paused, speed=e.speed,
                sim_time_s=e.sim_time, model=e.model_status, threshold_C=e.s.T_threshold_C)


@app.get("/api/status")
def status():
    return _status()


@app.post("/api/control")
def control(c: Control):
    try:
        app.state.engine.configure(**c.model_dump(exclude_none=True))
    except AssertionError as e:
        raise HTTPException(400, f"invalid value: {e}")
    return _status()


@app.get("/api/traces")
def traces():
    return dict(meta=app.state.engine.pack.meta, traces=app.state.engine.pack.index())


@app.post("/api/replay")
def replay(a: Assign):
    if a.series_id not in app.state.engine.pack.series:
        raise HTTPException(404, "unknown series_id")
    app.state.engine.assign_trace(a.gpu_id, a.series_id)
    return _status()


@app.get("/api/layout")
def layout():
    return app.state.engine.describe()


@app.get("/api/results")
def results():
    """Research results exactly as written by the experiment code; missing files are reported as missing."""
    out = {}
    for name in ("results.json", "audit_summary.json", "split_report.json", "e2_results.json",
                 "e2_results_preliminary.json", "e2_integration_demo.json", "e2_demo_highload_train_jobs.json",
                 "results_subset.json", "audit_summary_subset.json", "split_report_subset.json", "e2_results_subset.json"):
        f = REPORTS / name
        out[name] = json.loads(f.read_text()) if f.exists() else None
    return out
