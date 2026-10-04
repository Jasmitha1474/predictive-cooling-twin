"""End-to-end: the WebSocket streams frames computed by the engine from a replay pack."""
import json
import os
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
PACK = BACKEND / "data" / "replay_pack.parquet"
pytestmark = pytest.mark.skipif(not PACK.exists(), reason="no replay pack built")


def _client(model=""):
    os.environ["PCOOL_MODEL"] = model
    os.environ["PCOOL_REPLAY_PACK"] = str(PACK)
    from fastapi.testclient import TestClient
    import app.main as m
    return TestClient(m.app)


def test_ws_frames_are_engine_outputs_and_labelled():
    with _client() as c:
        with c.websocket_connect("/ws/telemetry") as ws:
            hello = json.loads(ws.receive_text())
            assert hello["type"] == "hello" and hello["model"]["state"] == "NOT_LOADED"
            f1, f2 = json.loads(ws.receive_text()), json.loads(ws.receive_text())
    g = f1["gpus"][0]
    assert set(g) >= {"measured", "predicted", "simulated", "workload", "trace"}
    assert g["predicted"]["source"] == "persistence_baseline_not_ml"
    assert f2["sim_time_s"] == f1["sim_time_s"] + 1
    # measured power is the recorded value at that trace index
    import pandas as pd
    tr = pd.read_parquet(PACK)
    row = tr[tr["series_id"] == g["trace"]["series_id"]].reset_index(drop=True).iloc[g["trace"]["t_index"]]
    assert abs(row["power_draw_W"] - g["measured"]["gpu_power"]) < 1e-3


def test_switching_controller_replays_same_workload():
    with _client() as c:
        r = c.post("/api/control", json={"controller_mode": "reactive"}).json()
        assert r["controller_mode"] == "reactive" and r["sim_time_s"] == 0
        assert c.post("/api/control", json={"mode": "NOT_A_MODE"}).status_code == 400
