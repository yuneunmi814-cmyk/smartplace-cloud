from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import SessionLocal, get_db
from app.core.security import get_approved_user
from app.models import Image, NaverAccount, Place, Task, TaskItem, User
from app.schemas import DispatchReq, OkRes, TaskItemRes, TaskRes
from app.services import audit
from app.services.queue import get_queue

router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])
settings = get_settings()


def _run_inline(task_id: int) -> None:
    """Process a task in-process (no Redis/worker). Uses its own DB session."""
    from app.worker.processor import process_task

    with SessionLocal() as db:
        process_task(db, task_id)


def _to_res(task: Task) -> TaskRes:
    return TaskRes(
        id=task.id,
        imageId=task.image_id,
        status=task.status,
        scheduledAt=task.scheduled_at,
        createdAt=task.created_at,
        finishedAt=task.finished_at,
        items=[
            TaskItemRes(
                id=it.id,
                placeId=it.place_id,
                status=it.status,
                attempts=it.attempts,
                errorMessage=it.error_message,
            )
            for it in task.items
        ],
    )


@router.post("/dispatch", response_model=TaskRes, status_code=status.HTTP_201_CREATED)
def dispatch(
    body: DispatchReq,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(get_approved_user),
) -> TaskRes:
    image = db.get(Image, body.imageId)
    if not image or image.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="이미지를 찾을 수 없습니다.")

    # Validate every target place belongs to the user.
    places = db.scalars(
        select(Place)
        .join(NaverAccount, NaverAccount.id == Place.account_id)
        .where(Place.id.in_(body.placeIds), NaverAccount.user_id == user.id)
    ).all()
    if len(places) != len(set(body.placeIds)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="유효하지 않은 가맹점이 포함되어 있습니다.")

    now = datetime.now(timezone.utc)
    scheduled = body.scheduledAt
    is_future = scheduled is not None and scheduled > now

    task = Task(
        user_id=user.id,
        image_id=image.id,
        status="pending" if is_future else "queued",
        scheduled_at=scheduled,
    )
    task.items = [TaskItem(place_id=p.id) for p in places]
    db.add(task)
    db.commit()
    db.refresh(task)

    # Enqueue immediately unless scheduled for the future (a beat scheduler
    # would enqueue future tasks when due).
    if not is_future:
        if settings.inline_dispatch:
            background.add_task(_run_inline, task.id)
        else:
            get_queue().enqueue({"taskId": task.id})

    audit.record(
        db,
        actor_user_id=user.id,
        action="task.dispatch",
        target_type="task",
        target_id=task.id,
        detail={"imageId": image.id, "placeIds": body.placeIds, "scheduled": is_future},
    )
    return _to_res(task)


@router.get("/{task_id}", response_model=TaskRes)
def get_task(
    task_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_approved_user),
) -> TaskRes:
    task = db.get(Task, task_id)
    if not task or task.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="작업을 찾을 수 없습니다.")
    return _to_res(task)


@router.get("", response_model=list[TaskRes])
def list_tasks(
    db: Session = Depends(get_db),
    user: User = Depends(get_approved_user),
) -> list[TaskRes]:
    rows = db.scalars(
        select(Task).where(Task.user_id == user.id).order_by(Task.id.desc())
    ).all()
    return [_to_res(t) for t in rows]


@router.patch("/{task_id}/cancel", response_model=TaskRes)
def cancel_task(
    task_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_approved_user),
) -> TaskRes:
    task = db.get(Task, task_id)
    if not task or task.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="작업을 찾을 수 없습니다.")
    if task.status not in ("pending", "queued"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="이미 처리 중이거나 완료된 작업입니다.")
    task.status = "canceled"
    db.commit()
    db.refresh(task)
    audit.record(
        db, actor_user_id=user.id, action="task.cancel", target_type="task", target_id=task.id
    )
    return _to_res(task)
