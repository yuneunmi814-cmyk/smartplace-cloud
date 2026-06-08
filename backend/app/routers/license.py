"""License issuance (admin) and offline activation (keyed by license key).

Activation is authenticated by the **license key itself** — the desktop app has
no cloud login, it just holds the key the customer was given. The key is the
bearer secret, so activation does not require a JWT."""

import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import get_current_user, require_role
from app.models import Device, License, Subscription, User
from app.schemas import (
    DeviceRes,
    LicenseActivateReq,
    LicenseActivateRes,
    LicenseCreateReq,
    LicenseDetailRes,
    LicenseRes,
)
from app.services import audit
from app.services.license_file import issue_license_file

router = APIRouter(prefix="/api/v1/license", tags=["license"])
settings = get_settings()


def _new_license_key() -> str:
    """Readable, hard-to-guess key, e.g. SPC-9F3A-12BC-77E0-A4D1."""
    blocks = "-".join(secrets.token_hex(2).upper() for _ in range(4))
    return f"SPC-{blocks}"


def _current_expiry(db: Session, lic: License) -> datetime:
    """Subscription period end if an active sub exists, else the license fallback."""
    sub = db.scalar(
        select(Subscription)
        .where(Subscription.user_id == lic.user_id, Subscription.status == "active")
        .order_by(Subscription.current_period_end.desc())
    )
    return sub.current_period_end if sub else lic.expires_at


@router.post("", response_model=LicenseRes, status_code=status.HTTP_201_CREATED)
def create_license(
    body: LicenseCreateReq,
    db: Session = Depends(get_db),
    admin: User = Depends(require_role("admin")),
) -> LicenseRes:
    user = db.scalar(select(User).where(User.email == body.email))
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "해당 이메일의 사용자가 없습니다.")
    days = body.days or settings.license_default_days
    lic = License(
        user_id=user.id,
        license_key=_new_license_key(),
        plan=body.plan,
        seats=body.seats,
        status="active",
        expires_at=datetime.now(timezone.utc) + timedelta(days=days),
    )
    db.add(lic)
    db.commit()
    db.refresh(lic)
    audit.record(
        db,
        actor_user_id=admin.id,
        action="license.create",
        target_type="license",
        target_id=lic.id,
        detail={"email": body.email, "plan": body.plan, "seats": body.seats},
    )
    return LicenseRes(
        id=lic.id,
        licenseKey=lic.license_key,
        plan=lic.plan,
        seats=lic.seats,
        status=lic.status,
        expiresAt=lic.expires_at,
        devicesUsed=0,
    )


def _detail(lic: License) -> LicenseDetailRes:
    return LicenseDetailRes(
        id=lic.id,
        licenseKey=lic.license_key,
        plan=lic.plan,
        seats=lic.seats,
        status=lic.status,
        expiresAt=lic.expires_at,
        devices=[
            DeviceRes(
                id=d.id,
                fingerprint=d.fingerprint,
                name=d.name,
                createdAt=d.created_at,
                lastSeenAt=d.last_seen_at,
            )
            for d in lic.devices
        ],
    )


@router.get("/mine", response_model=list[LicenseDetailRes])
def my_licenses(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> list[LicenseDetailRes]:
    """The caller's own licenses, each with its activated devices/seats."""
    rows = db.scalars(
        select(License).where(License.user_id == user.id).order_by(License.id.desc())
    ).all()
    return [_detail(lic) for lic in rows]


def _owned_license(license_id: int, db: Session, user: User) -> License:
    lic = db.get(License, license_id)
    if not lic:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "라이선스를 찾을 수 없습니다.")
    if lic.user_id != user.id and user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "권한이 없습니다.")
    return lic


@router.delete("/{license_id}/devices/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_device(
    license_id: int,
    device_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    """Release a seat by removing a bound device (owner or admin)."""
    lic = _owned_license(license_id, db, user)
    device = db.get(Device, device_id)
    if not device or device.license_id != lic.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "기기를 찾을 수 없습니다.")
    db.delete(device)
    db.commit()
    audit.record(
        db,
        actor_user_id=user.id,
        action="license.device.deactivate",
        target_type="device",
        target_id=device_id,
        detail={"licenseId": lic.id, "fingerprint": device.fingerprint[:16]},
    )


@router.post("/{license_id}/revoke", response_model=LicenseDetailRes)
def revoke_license(
    license_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_role("admin")),
) -> LicenseDetailRes:
    """Admin disables a license entirely — future activations are rejected."""
    lic = db.get(License, license_id)
    if not lic:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "라이선스를 찾을 수 없습니다.")
    lic.status = "revoked"
    db.commit()
    db.refresh(lic)
    audit.record(
        db,
        actor_user_id=admin.id,
        action="license.revoke",
        target_type="license",
        target_id=lic.id,
    )
    return _detail(lic)


@router.post("/activate", response_model=LicenseActivateRes)
def activate(body: LicenseActivateReq, db: Session = Depends(get_db)) -> LicenseActivateRes:
    lic = db.scalar(select(License).where(License.license_key == body.licenseKey))
    if not lic or lic.status != "active":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "유효하지 않은 라이선스입니다.")

    fp = body.deviceFingerprint
    device = db.scalar(
        select(Device).where(Device.license_id == lic.id, Device.fingerprint == fp)
    )
    if device is None:
        used = db.scalars(select(Device).where(Device.license_id == lic.id)).all()
        if len(used) >= lic.seats:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"좌석을 모두 사용했습니다 ({lic.seats}대). 다른 기기를 해제하세요.",
            )
        device = Device(license_id=lic.id, fingerprint=fp, name=body.deviceName)
        db.add(device)

    device.last_seen_at = datetime.now(timezone.utc)
    expiry = _current_expiry(db, lic)
    db.commit()

    lf = issue_license_file(
        settings.license_private_key,
        license_key=lic.license_key,
        plan=lic.plan,
        device_fingerprint=fp,
        expiry=expiry,
        seats=lic.seats,
    )
    audit.record(
        db,
        actor_user_id=lic.user_id,
        action="license.activate",
        target_type="license",
        target_id=lic.id,
        detail={"fingerprint": fp[:16], "device": body.deviceName},
    )
    return LicenseActivateRes(licenseFile=lf, expiry=expiry, plan=lic.plan, seats=lic.seats)
