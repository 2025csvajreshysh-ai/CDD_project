"""Authenticated, tenant-aware WebSocket event delivery."""
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional, Set

from fastapi import WebSocket


@dataclass(frozen=True)
class Connection:
    role: str
    user_id: int
    restaurant_ids: frozenset[int]


class ConnectionManager:
    def __init__(self) -> None:
        self.connections: Dict[WebSocket, Connection] = {}

    async def connect(
        self,
        websocket: WebSocket,
        *,
        role: str,
        user_id: int,
        restaurant_ids: Iterable[int] = (),
    ) -> None:
        await websocket.accept()
        self.connections[websocket] = Connection(
            role=role,
            user_id=user_id,
            restaurant_ids=frozenset(restaurant_ids),
        )

    def disconnect(self, websocket: WebSocket) -> None:
        self.connections.pop(websocket, None)

    async def broadcast(
        self,
        message: Dict[str, Any],
        *,
        restaurant_id: Optional[int] = None,
        user_ids: Iterable[Optional[int]] = (),
    ) -> None:
        """Send staff events to authorized staff and private updates to named users."""
        recipients: Set[WebSocket] = set()
        private_user_ids = {user_id for user_id in user_ids if user_id is not None}

        for websocket, connection in tuple(self.connections.items()):
            is_global_staff = connection.role in {"kitchen_staff", "super_admin"}
            is_restaurant_admin = (
                connection.role == "restaurant_admin"
                and restaurant_id is not None
                and restaurant_id in connection.restaurant_ids
            )
            if is_global_staff or is_restaurant_admin or connection.user_id in private_user_ids:
                recipients.add(websocket)

        stale = []
        for websocket in recipients:
            try:
                await websocket.send_json(message)
            except Exception:
                stale.append(websocket)
        for websocket in stale:
            self.disconnect(websocket)

    async def send_to_user(self, user_id: int, message: Dict[str, Any]) -> None:
        stale = []
        for websocket, connection in tuple(self.connections.items()):
            if connection.user_id != user_id:
                continue
            try:
                await websocket.send_json(message)
            except Exception:
                stale.append(websocket)
        for websocket in stale:
            self.disconnect(websocket)


manager = ConnectionManager()
