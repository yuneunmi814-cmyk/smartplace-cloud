"""Task processing core.

Separated from the queue loop so it can be unit-tested directly. Implements the
Retry Policy the design calls out: each place is attempted up to
`task_max_retries` times with linear backoff before being marked failed. Every
outcome is written to the audit trail (log transparency)."""

import time
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.crypto import decrypt
from app.models import Image, NaverAccount, Place, Task, TaskItem
from app.services import audit
from app.services.naver_gateway import GatewayError, get_gateway
from app.services.storage import get_storage

settings = get_settings()


def process_task(db: Session, task_id: int) -> str:
    """Processes one dispatch task. Returns the final task status."""
    task = db.get(Task, task_id)
    if task is None or task.status in ("canceled", "success", "partial", "failed"):
        return task.status if task else "missing"

    task.status = "running"
    db.commit()

    image = db.get(Image, task.image_id)
    image_url = get_storage().presigned_url(image.s3_key) if image else ""
    gateway = get_gateway()

    ok_count = 0
    fail_count = 0
    for item in task.items:
        if _apply_item(db, gateway, item, image_url):
            ok_count += 1
        else:
            fail_count += 1

    task.status = "success" if fail_count == 0 else "failed" if ok_count == 0 else "partial"
    task.finished_at = datetime.now(timezone.utc)
    db.commit()

    audit.record(
        db,
        actor_user_id=task.user_id,
        action="task.processed",
        target_type="task",
        target_id=task.id,
        detail={"status": task.status, "ok": ok_count, "fail": fail_count},
    )
    return task.status


def _apply_item(db: Session, gateway, item: TaskItem, image_url: str) -> bool:
    place = db.get(Place, item.place_id)
    account = db.get(NaverAccount, place.account_id) if place else None
    if not place or not account:
        item.status = "fail"
        item.error_message = "place or account missing"
        db.commit()
        return False

    token = decrypt(account.encrypted_token)
    last_error = ""
    for attempt in range(1, settings.task_max_retries + 1):
        item.attempts = attempt
        try:
            gateway.apply_main_image(token, place.place_id, image_url)
            item.status = "ok"
            item.error_message = None
            db.commit()
            return True
        except GatewayError as exc:
            last_error = str(exc)
            if attempt < settings.task_max_retries:
                time.sleep(settings.task_retry_backoff_seconds * attempt)  # linear backoff

    item.status = "fail"
    item.error_message = last_error
    db.commit()
    return False
