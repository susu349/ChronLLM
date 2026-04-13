import asyncio
import json
from datetime import datetime
from typing import Set
from fastapi import Request


class SSEManager:
    def __init__(self):
        self.active_connections: Set[asyncio.Queue] = set()

    async def connect(self) -> asyncio.Queue:
        queue = asyncio.Queue(maxsize=100)
        self.active_connections.add(queue)
        return queue

    def disconnect(self, queue: asyncio.Queue):
        self.active_connections.discard(queue)

    async def broadcast(self, event_type: str, data: dict):
        message = {
            "type": event_type,
            "data": data,
            "timestamp": datetime.now().isoformat()
        }
        disconnected = []
        for queue in self.active_connections:
            try:
                queue.put_nowait(message)
            except asyncio.QueueFull:
                disconnected.append(queue)
            except Exception:
                disconnected.append(queue)
        for q in disconnected:
            self.disconnect(q)


# 全局单例
_sse_manager = None


def get_sse_manager() -> SSEManager:
    global _sse_manager
    if _sse_manager is None:
        _sse_manager = SSEManager()
    return _sse_manager
