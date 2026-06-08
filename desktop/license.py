"""오프라인 라이선스 검증 (데스크톱 측).

서버는 Ed25519 **개인키**로 라이선스 파일을 서명하고, 이 앱은 아래 **공개키**로만
검증합니다. 공개키는 위조가 불가능하므로 앱에 그대로 넣어도 안전합니다.

흐름:
  1) 온라인이면  activate_online()  →  /license/activate 호출 → 서명된 파일 캐시
  2) 오프라인이면 load_cached()      →  마지막으로 받은 파일 사용
  3) verify()로 서명·만료·기기 검증 통과해야 기능이 열립니다.
"""

import base64
import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib import error, request

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

# 서버 scripts/gen_license_keys.py 가 출력하는 공개키. (개발용 기본 키쌍)
# 프로덕션 배포 시 새 키쌍을 발급해 이 값과 서버 .env 를 함께 교체하세요.
PUBLIC_KEY_HEX = "82b12111ef3ff4f69260f17829ab190e0a1a49aafe642f9af506e314d90862ee"

# 서명 메시지 접두사 — 서버(license_file.py)와 1바이트도 달라선 안 됩니다.
SIGN_PREFIX = b"license/"

_HOME = Path.home() / ".smartplace_beta"
LICENSE_CACHE = _HOME / "license.lic"
_DEVICE_ID_FILE = _HOME / "device.id"
_LAST_SEEN_FILE = _HOME / "last_verified"  # 시계 되돌리기 완화용

_BEGIN = "-----BEGIN LICENSE FILE-----"
_END = "-----END LICENSE FILE-----"

DEFAULT_SERVER = "http://localhost:8000"


# ---- 기기 핑거프린트 -------------------------------------------------------
def device_fingerprint() -> str:
    """재부팅·업데이트에도 동일한 안정적 기기 식별자.

    휘발성 값(IP·임시 호스트명 등)을 넣지 않고, 최초 1회 생성한 난수 UUID를
    파일로 보관해 그 해시를 사용합니다."""
    _HOME.mkdir(parents=True, exist_ok=True)
    if _DEVICE_ID_FILE.exists():
        raw = _DEVICE_ID_FILE.read_text().strip()
    else:
        raw = uuid.uuid4().hex
        _DEVICE_ID_FILE.write_text(raw)
    return hashlib.sha256(raw.encode()).hexdigest()


# ---- 검증 ------------------------------------------------------------------
def verify(license_file: str, *, fingerprint: str | None = None) -> dict:
    """서명·기기·만료 검증. 통과 시 payload(dict) 반환, 실패 시 ValueError."""
    fingerprint = fingerprint or device_fingerprint()
    body = license_file.replace(_BEGIN, "").replace(_END, "").strip()
    try:
        env = json.loads(base64.b64decode(body))
    except (ValueError, json.JSONDecodeError) as exc:
        raise ValueError("라이선스 파일 형식이 올바르지 않습니다") from exc
    if env.get("alg") != "ed25519":
        raise ValueError("지원하지 않는 서명 알고리즘")
    data_b64, sig_b64 = env["data"], env["sig"]

    pub = Ed25519PublicKey.from_public_bytes(bytes.fromhex(PUBLIC_KEY_HEX))
    try:
        pub.verify(base64.b64decode(sig_b64), SIGN_PREFIX + data_b64.encode())
    except InvalidSignature as exc:
        raise ValueError("서명 검증 실패 — 위변조된 라이선스") from exc

    p = json.loads(base64.b64decode(data_b64))
    now = datetime.now(timezone.utc)
    if p["deviceFingerprint"] != fingerprint:
        raise ValueError("다른 기기에서 발급된 라이선스입니다")
    if datetime.fromisoformat(p["issued"]) > now:
        raise ValueError("발급일이 미래입니다 — 시스템 시계를 확인하세요")
    if datetime.fromisoformat(p["expiry"]) < now:
        raise ValueError("구독이 만료되었습니다")
    _guard_clock_rollback(now)
    return p


def _guard_clock_rollback(now: datetime) -> None:
    """온라인 검증 시각을 기록해, PC 시계를 그보다 과거로 되돌리면 거부.
    (완전 차단은 불가 — 오프라인 라이선싱의 알려진 한계)"""
    try:
        if _LAST_SEEN_FILE.exists():
            last = datetime.fromisoformat(_LAST_SEEN_FILE.read_text().strip())
            if now < last:
                raise ValueError("시스템 시계가 과거로 되돌려졌습니다")
    except ValueError:
        raise
    except Exception:  # noqa: BLE001 — 손상된 파일은 무시
        pass


def _stamp_verified(now: datetime | None = None) -> None:
    now = now or datetime.now(timezone.utc)
    _HOME.mkdir(parents=True, exist_ok=True)
    _LAST_SEEN_FILE.write_text(now.isoformat())


# ---- 캐시 ------------------------------------------------------------------
def cache(license_file: str) -> None:
    _HOME.mkdir(parents=True, exist_ok=True)
    LICENSE_CACHE.write_text(license_file)


def load_cached() -> str | None:
    return LICENSE_CACHE.read_text() if LICENSE_CACHE.exists() else None


# ---- 온라인 활성화 ---------------------------------------------------------
def activate_online(license_key: str, *, server: str = DEFAULT_SERVER,
                    device_name: str | None = None, timeout: int = 15) -> str:
    """/license/activate 호출 → 서명된 라이선스 파일을 받아 캐시하고 반환."""
    payload = json.dumps({
        "licenseKey": license_key,
        "deviceFingerprint": device_fingerprint(),
        "deviceName": device_name,
    }).encode()
    req = request.Request(
        f"{server.rstrip('/')}/api/v1/license/activate",
        data=payload, headers={"Content-Type": "application/json"}, method="POST",
    )
    with request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read())
    lf = data["licenseFile"]
    cache(lf)
    return lf


def status(license_key: str | None = None, *, server: str = DEFAULT_SERVER) -> dict:
    """UI 표시용 상태 dict. 네트워크 실패해도 예외를 던지지 않습니다.
    key를 주면 온라인 활성화를 시도하고, 없으면 캐시만 검증합니다."""
    try:
        p = ensure_licensed(license_key, server=server)
        return {"licensed": True, "plan": p.get("plan"), "expiry": p.get("expiry")}
    except ValueError as exc:
        return {"licensed": False, "reason": str(exc)}
    except Exception as exc:  # noqa: BLE001
        return {"licensed": False, "reason": f"확인 실패: {exc}"}


def ensure_licensed(license_key: str | None = None, *, server: str = DEFAULT_SERVER) -> dict:
    """부팅 게이트. 온라인이면 갱신 후 검증, 오프라인이면 캐시로 검증.
    성공 시 payload 반환, 실패 시 ValueError(사용자에게 보여줄 메시지)."""
    lf = None
    if license_key:
        try:
            lf = activate_online(license_key, server=server)
        except (error.URLError, OSError):
            lf = None  # 오프라인 — 캐시로 폴백
    if lf is None:
        lf = load_cached()
    if not lf:
        raise ValueError("라이선스가 없습니다. 라이선스 키를 입력해 활성화하세요.")
    payload = verify(lf)
    _stamp_verified()
    return payload
