"""Queue-consuming worker process.

Run with:  python -m app.worker.worker
Consumes task ids from Redis and processes them. Scale by running N copies.
"""

import logging

from app.core.database import Base, SessionLocal, engine
from app.services.queue import get_queue
from app.worker.processor import process_task

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s worker: %(message)s")
log = logging.getLogger(__name__)


def run() -> None:
    Base.metadata.create_all(bind=engine)
    queue = get_queue()
    log.info("worker started, waiting for tasks…")
    while True:
        payload = queue.dequeue(timeout=5)
        if not payload:
            continue
        task_id = payload.get("taskId")
        if task_id is None:
            log.warning("invalid payload: %s", payload)
            continue
        with SessionLocal() as db:
            try:
                status = process_task(db, task_id)
                log.info("task %s -> %s", task_id, status)
            except Exception:  # noqa: BLE001 — worker must never crash the loop
                log.exception("task %s failed unexpectedly", task_id)


if __name__ == "__main__":
    run()
