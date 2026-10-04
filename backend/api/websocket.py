from fastapi import WebSocket
from typing import List
import orjson
import asyncio

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        text = orjson.dumps(message).decode('utf-8')
        dead_connections = []
        for connection in self.active_connections:
            try: await connection.send_text(text)
            except Exception: dead_connections.append(connection)
        for dead in dead_connections: self.disconnect(dead)

manager = ConnectionManager()
