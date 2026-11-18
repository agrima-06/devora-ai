"""Workflow event broadcaster and Server-Sent Events (SSE) streaming infrastructure."""
import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.logging import get_logger
from app.models.workflow_event import WorkflowEvent

logger = get_logger("workflow_events")


class WorkflowEventBroadcaster:
    """Manages active streaming subscribers and event broadcasting per task."""

    _instance: Optional["WorkflowEventBroadcaster"] = None

    def __init__(self):
        # Maps task_id str -> List of asyncio.Queue
        self._subscribers: Dict[str, List[asyncio.Queue]] = {}

    @classmethod
    def get_instance(cls) -> "WorkflowEventBroadcaster":
        """Get or initialize singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def subscribe(self, task_id: str) -> asyncio.Queue:
        """Register a new SSE client queue for a task."""
        queue: asyncio.Queue = asyncio.Queue()
        if task_id not in self._subscribers:
            self._subscribers[task_id] = []
        self._subscribers[task_id].append(queue)
        logger.info("subscriber_connected", task_id=task_id, total_subscribers=len(self._subscribers[task_id]))
        return queue

    def unsubscribe(self, task_id: str, queue: asyncio.Queue) -> None:
        """Remove an SSE client queue upon disconnection."""
        if task_id in self._subscribers:
            if queue in self._subscribers[task_id]:
                self._subscribers[task_id].remove(queue)
            if not self._subscribers[task_id]:
                del self._subscribers[task_id]
        logger.info("subscriber_disconnected", task_id=task_id)

    async def emit(
        self,
        task_id: str,
        event_type: str,
        message: str,
        agent_name: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
        db: Optional[AsyncSession] = None,
    ) -> Dict[str, Any]:
        """Broadcast an event to all connected clients and persist in database if session provided."""
        event_data = {
            "task_id": task_id,
            "event_type": event_type,
            "agent_name": agent_name,
            "message": message,
            "payload": payload or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # 1. Broadcast to in-memory queues
        queues = self._subscribers.get(task_id, [])
        for q in list(queues):
            try:
                q.put_nowait(event_data)
            except Exception as e:
                logger.warning("failed_to_queue_event", task_id=task_id, error=str(e))

        # 2. Persist to database
        if db is not None:
            try:
                event_rec = WorkflowEvent(
                    task_id=uuid.UUID(task_id),
                    event_type=event_type,
                    agent_name=agent_name,
                    message=message,
                    payload=payload or {},
                )
                db.add(event_rec)
                await db.flush()
            except Exception as db_err:
                logger.error("failed_to_persist_workflow_event", task_id=task_id, error=str(db_err))

        return event_data

    async def event_generator(self, task_id: str) -> AsyncGenerator[str, None]:
        """Async generator yielding Server-Sent Events (SSE) formatted text."""
        queue = self.subscribe(task_id)
        try:
            # Yield initial connection confirmation
            init_payload = json.dumps({
                "task_id": task_id,
                "event_type": "CONNECTED",
                "message": "Connected to Devora AI workflow live stream",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            yield f"data: {init_payload}\n\n"

            while True:
                # Wait for next event or heartbeat
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=25.0)
                    yield f"data: {json.dumps(event)}\n\n"
                    # If terminal event, exit
                    if event.get("event_type") in ("COMPLETED", "FAILED", "CANCELLED"):
                        break
                except asyncio.TimeoutError:
                    # Send keep-alive heartbeat comment
                    yield ": ping\n\n"
        finally:
            self.unsubscribe(task_id, queue)
