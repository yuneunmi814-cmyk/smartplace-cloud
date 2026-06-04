import uuid

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_approved_user
from app.models import Image, User
from app.schemas import ImageRes
from app.services import audit
from app.services.storage import Storage, get_storage

router = APIRouter(prefix="/api/v1/images", tags=["images"])
ALLOWED = {"image/jpeg", "image/png", "image/webp"}


async def _store_one(file: UploadFile, db: Session, user: User) -> Image:
    content_type = file.content_type or "application/octet-stream"
    data = await file.read()

    key = f"users/{user.id}/images/{uuid.uuid4().hex}-{file.filename}"
    get_storage().upload(key, data, content_type)

    image = Image(
        user_id=user.id,
        s3_key=key,
        original_filename=file.filename or "upload",
        content_type=content_type,
        size_bytes=len(data),
    )
    db.add(image)
    db.commit()
    db.refresh(image)
    audit.record(
        db, actor_user_id=user.id, action="image.upload", target_type="image", target_id=image.id
    )
    return image


def _to_res(image: Image, storage: Storage) -> ImageRes:
    return ImageRes(
        id=image.id,
        originalFilename=image.original_filename,
        contentType=image.content_type,
        sizeBytes=image.size_bytes,
        url=storage.presigned_url(image.s3_key),
    )


@router.post("/upload", response_model=ImageRes, status_code=201)
async def upload_image(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_approved_user),
) -> ImageRes:
    image = await _store_one(file, db, user)
    return _to_res(image, get_storage())


@router.post("/upload-batch", response_model=list[ImageRes], status_code=201)
async def upload_images(
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_approved_user),
) -> list[ImageRes]:
    """Uploads multiple images in one request."""
    storage = get_storage()
    results: list[ImageRes] = []
    for file in files:
        image = await _store_one(file, db, user)
        results.append(_to_res(image, storage))
    return results


@router.get("", response_model=list[ImageRes])
def list_images(
    db: Session = Depends(get_db),
    user: User = Depends(get_approved_user),
) -> list[ImageRes]:
    rows = db.scalars(
        select(Image).where(Image.user_id == user.id).order_by(Image.id.desc())
    ).all()
    storage = get_storage()
    return [_to_res(i, storage) for i in rows]
