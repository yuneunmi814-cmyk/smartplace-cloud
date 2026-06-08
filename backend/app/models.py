"""Cloud ORM models. Multi-account, enterprise-oriented.

Naver tokens are stored AES-256-GCM encrypted (NaverAccount.encrypted_token).
AuditLog is append-only for a tamper-evident trail (senior advice: log
transparency)."""

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(16), default="user")  # admin | user
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending | approved | disabled
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    naver_accounts: Mapped[list["NaverAccount"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class NaverAccount(Base):
    __tablename__ = "naver_accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    alias: Mapped[str] = mapped_column(String(120))
    # AES-256-GCM ciphertext of the Naver session/API token. Never plaintext.
    encrypted_token: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="connected")  # connected | revoked
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    user: Mapped["User"] = relationship(back_populates="naver_accounts")
    places: Mapped[list["Place"]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )


class Place(Base):
    __tablename__ = "places"

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("naver_accounts.id", ondelete="CASCADE"), index=True
    )
    place_id: Mapped[str] = mapped_column(String(64), index=True)  # Naver business id
    business_name: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    account: Mapped["NaverAccount"] = relationship(back_populates="places")


class Image(Base):
    __tablename__ = "images"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    s3_key: Mapped[str] = mapped_column(String(512))
    original_filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class Task(Base):
    """A dispatch batch: one image → many places, processed asynchronously."""

    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    image_id: Mapped[int] = mapped_column(ForeignKey("images.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    # pending | queued | running | success | partial | failed | canceled
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    items: Mapped[list["TaskItem"]] = relationship(
        back_populates="task", cascade="all, delete-orphan"
    )


class TaskItem(Base):
    __tablename__ = "task_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), index=True)
    place_id: Mapped[int] = mapped_column(ForeignKey("places.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending|ok|fail
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    task: Mapped["Task"] = relationship(back_populates="items")


class License(Base):
    """A purchasable license key. Seats = how many devices may activate it.

    Expiry is driven by the user's subscription (see Subscription); ``expires_at``
    here is the offline fallback used when no active subscription exists."""

    __tablename__ = "licenses"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    license_key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    plan: Mapped[str] = mapped_column(String(32), default="basic")
    seats: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(16), default="active")  # active | suspended | revoked
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    devices: Mapped[list["Device"]] = relationship(
        back_populates="license", cascade="all, delete-orphan"
    )


class Device(Base):
    """A machine bound to a license via a stable fingerprint (seat consumption)."""

    __tablename__ = "devices"
    __table_args__ = (UniqueConstraint("license_id", "fingerprint", name="uq_device_license_fp"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    license_id: Mapped[int] = mapped_column(
        ForeignKey("licenses.id", ondelete="CASCADE"), index=True
    )
    fingerprint: Mapped[str] = mapped_column(String(128), index=True)
    name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    license: Mapped["License"] = relationship(back_populates="devices")


class Subscription(Base):
    """Billing state. ``current_period_end`` becomes the license file ``expiry``.

    Renewal/cancellation webhooks from the payment provider update this row; the
    next license activation picks up the new period end automatically."""

    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(24), default="mock")  # mock | lemonsqueezy | stripe | toss
    provider_subscription_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    plan: Mapped[str] = mapped_column(String(32), default="basic")
    status: Mapped[str] = mapped_column(String(16), default="active")  # active | canceled | past_due
    current_period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )


class AuditLog(Base):
    """Append-only audit trail. No updates/deletes in normal operation."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    actor_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(64), index=True)
    target_type: Mapped[str] = mapped_column(String(32))
    target_id: Mapped[str] = mapped_column(String(64))
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)
