from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, model_validator


# ---- Auth ------------------------------------------------------------------
class SignupReq(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class LoginReq(BaseModel):
    email: EmailStr
    password: str


class TokenPair(BaseModel):
    accessToken: str
    refreshToken: str
    role: str
    status: str


class RefreshReq(BaseModel):
    refreshToken: str


class AccessTokenRes(BaseModel):
    accessToken: str


class UserRes(BaseModel):
    id: int
    email: EmailStr
    role: str
    status: str

    class Config:
        from_attributes = True


# ---- Naver accounts --------------------------------------------------------
class NaverAccountCreateReq(BaseModel):
    alias: str
    # Provide EITHER an opaque session token OR a Naver loginId + loginPw.
    # Whatever is provided is stored AES-256 encrypted at rest.
    token: str | None = None
    loginId: str | None = None
    loginPw: str | None = None

    @model_validator(mode="after")
    def _require_credential(self) -> "NaverAccountCreateReq":
        if not self.token and not (self.loginId and self.loginPw):
            raise ValueError("token 또는 (loginId, loginPw) 중 하나는 필수입니다.")
        return self


class NaverAccountRes(BaseModel):
    id: int
    alias: str
    status: str
    createdAt: datetime


# ---- Places ----------------------------------------------------------------
class PlaceRes(BaseModel):
    id: int
    accountId: int
    placeId: str
    businessName: str


# ---- Images ----------------------------------------------------------------
class ImageRes(BaseModel):
    id: int
    originalFilename: str
    contentType: str
    sizeBytes: int
    url: str


# ---- Tasks -----------------------------------------------------------------
class DispatchReq(BaseModel):
    imageId: int
    placeIds: list[int] = Field(min_length=1)
    scheduledAt: datetime | None = None


class TaskItemRes(BaseModel):
    id: int
    placeId: int
    status: str
    attempts: int
    errorMessage: str | None


class TaskRes(BaseModel):
    id: int
    imageId: int
    status: str
    scheduledAt: datetime | None
    createdAt: datetime
    finishedAt: datetime | None
    items: list[TaskItemRes]


# ---- Admin / audit ---------------------------------------------------------
class OkRes(BaseModel):
    ok: bool


class AuditLogRes(BaseModel):
    id: int
    actorUserId: int | None
    action: str
    targetType: str
    targetId: str
    detail: str | None
    createdAt: datetime


class StatsRes(BaseModel):
    totalTasks: int
    successRate: float
    pendingTasks: int
    users: int


# ---- License / subscription -----------------------------------------------
class LicenseCreateReq(BaseModel):
    """Admin issues a license for a user (by email)."""

    email: EmailStr
    plan: str = "basic"
    seats: int = Field(default=1, ge=1, le=100)
    days: int | None = Field(default=None, ge=1)  # falls back to license_default_days


class LicenseRes(BaseModel):
    id: int
    licenseKey: str
    plan: str
    seats: int
    status: str
    expiresAt: datetime
    devicesUsed: int


class LicenseActivateReq(BaseModel):
    licenseKey: str
    deviceFingerprint: str = Field(min_length=8, max_length=128)
    deviceName: str | None = Field(default=None, max_length=120)


class LicenseActivateRes(BaseModel):
    licenseFile: str
    expiry: datetime
    plan: str
    seats: int


class SubscribeReq(BaseModel):
    """Mock checkout — starts/renews a subscription for the given license owner."""

    email: EmailStr
    plan: str = "basic"
    months: int = Field(default=1, ge=1, le=36)
