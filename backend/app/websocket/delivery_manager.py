from collections import defaultdict
from fastapi import WebSocket


class DeliveryConnectionManager:
    def __init__(self):
        self.connections = defaultdict(lambda: {"partner": set(), "customer": set()})

    async def connect(self, order_id: int, role: str, websocket: WebSocket):
        await websocket.accept()
        self.connections[order_id][role].add(websocket)

    def disconnect(self, order_id: int, websocket: WebSocket):
        for peers in self.connections.get(order_id, {}).values():
            peers.discard(websocket)
        if order_id in self.connections and not any(self.connections[order_id].values()):
            self.connections.pop(order_id, None)

    async def broadcast(self, order_id: int, message: dict):
        stale = []
        for websocket in tuple(self.connections.get(order_id, {}).get("customer", set())):
            try:
                await websocket.send_json(message)
            except Exception:
                stale.append(websocket)
        for websocket in stale:
            self.disconnect(order_id, websocket)


delivery_manager = DeliveryConnectionManager()
