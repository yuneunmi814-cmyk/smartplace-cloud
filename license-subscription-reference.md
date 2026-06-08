# 데스크톱 라이선스 / 구독 결제 — 구현 청사진 (reference)

> 레퍼런스: **Keygen** (keygen-sh, 소프트웨어 라이선싱의 사실상 표준)
> 분석한 실제 소스: `keygen-sh/air-gapped-activation-example` (MIT) — 라이선스 파일 서명·검증 패턴
> 목적: 우리 **데스크톱 앱(`desktop/`, Python)** 을 구독형으로 만들기. 클라우드(`cloud/backend`, FastAPI)는
> 이미 `License/Device/Subscription/Payment` 모델 + billing 뼈대가 있음.

---

## 0. 한 줄 요약
- 클라우드가 **Ed25519 개인키로 "라이선스 파일"을 서명** → 데스크톱은 **공개키로 오프라인 검증**.
- 파일 안에 `expiry`(=구독 만료일)와 `deviceFingerprint`를 넣어 **만료·기기 바인딩**을 한 번에 처리.
- 결제(구독)는 webhook으로 `subscription.current_period_end`를 갱신 → 그 값이 라이선스 파일 `expiry`가 됨.

## 1. 레퍼런스 ↔ 우리 프로젝트 매핑표

| Keygen 개념 | 우리 구현 위치 | 상태 |
|---|---|---|
| License (키 발급) | `cloud/backend/app/models.py::License` | 있음 |
| Machine activation (기기 바인딩) | `models.py::Device` + `routers/license.py::bind` | 있음 |
| **License/Machine File (서명된 오프라인 파일)** | **신규: `app/services/license_file.py`** | **만들 것** |
| 서명 알고리즘 | 현재 `license.py::sign_license` = **HMAC(대칭)** | **Ed25519(비대칭)로 교체** |
| 오프라인 검증(클라이언트) | **신규: `desktop/license.py`** | **만들 것** |
| Subscription → 만료 | `models.py::Subscription` + `routers/billing.py` webhook | 뼈대 있음 |
| 결제 프로바이더 | `app/billing/provider.py` (Mock/교체식) | 있음 (Toss/Stripe/LemonSqueezy로 교체) |

## 2. 결정적 차이 (그래서 우리는 이렇게 바꾼다)

1. **HMAC → Ed25519 (가장 중요).**
   현재 `sign_license`는 HMAC이라, **데스크톱이 검증하려면 같은 비밀키를 들고 있어야** 함 = 비밀키 유출 = 누구나 위조 가능.
   Keygen 방식은 **비대칭**: 클라우드만 **개인키**로 서명, 앱엔 **공개키**만 내장 → 앱이 털려도 위조 불가. **반드시 이걸로 간다.**

2. **"검증 + 결제"를 라이선스 파일 하나로 통합.**
   별도 상태조회 없이, 서명된 파일의 `expiry`만 보면 구독 유효성 판정 끝. 오프라인에서도 됨.

3. **우리는 Keygen보다 단순해도 됨.**
   - Keygen은 `aes-256-gcm+ed25519`(서명+암호화)까지 지원 → 우리는 **서명만(ed25519)** 으로 MVP. (기기 바인딩은 payload 안 `deviceFingerprint` 필드로 충분. 암호화는 "내용 숨김"용 선택적 강화.)
   - 에어갭/QR 활성화는 **불필요**(우리 사용자는 인터넷 됨). 온라인 발급 + 오프라인 캐시면 충분.

## 3. 그대로 베껴 쓸 코드 (우리 경로로 치환)

### (A) 키쌍 1회 생성 — `cloud/backend/scripts/gen_license_keys.py`
```python
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, PublicFormat, NoEncryption

priv = Ed25519PrivateKey.generate()
priv_hex = priv.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption()).hex()
pub_hex = priv.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()
print("개인키(서버 .env 에만):  SMARTPLACE_LICENSE_PRIVATE_KEY=" + priv_hex)
print("공개키(앱에 내장):        " + pub_hex)
```
> 개인키는 **서버 `.env`/시크릿 매니저에만**. 공개키는 데스크톱 코드에 상수로 박아도 안전.

### (B) 클라우드: 라이선스 파일 발급 — `cloud/backend/app/services/license_file.py`
```python
import base64, json
from datetime import datetime, timezone
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

SIGN_PREFIX = b"license/"   # ← Keygen이 "machine/" 쓰듯, 서명 메시지 접두사 (검증 측과 반드시 일치)

def issue_license_file(priv_hex: str, *, license_key: str, plan: str,
                       device_fingerprint: str, expiry: datetime, seats: int) -> str:
    payload = {
        "licenseKey": license_key,
        "plan": plan,
        "deviceFingerprint": device_fingerprint,
        "issued": datetime.now(timezone.utc).isoformat(),
        "expiry": expiry.astimezone(timezone.utc).isoformat(),
        "seats": seats,
    }
    data_b64 = base64.b64encode(json.dumps(payload).encode()).decode()
    priv = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(priv_hex))
    sig_b64 = base64.b64encode(priv.sign(SIGN_PREFIX + data_b64.encode())).decode()
    envelope = base64.b64encode(json.dumps(
        {"data": data_b64, "sig": sig_b64, "alg": "ed25519"}).encode()).decode()
    return f"-----BEGIN LICENSE FILE-----\n{envelope}\n-----END LICENSE FILE-----"
```

### (C) 클라우드: 발급 엔드포인트 — `cloud/backend/app/routers/license.py` 에 추가
```python
# POST /api/v1/license/activate  { licenseKey, deviceFingerprint }
# - 기존 bind(좌석수 검증) 후, 구독 만료일로 라이선스 파일 발급
@router.post("/activate")
def activate(body: LicenseBindReq, db: Session = Depends(get_db),
             user_id: int = Depends(get_current_user_id)):
    lic = db.scalar(select(License).where(License.license_key == body.licenseKey))
    if not lic or lic.status != "active":
        raise HTTPException(403, "유효하지 않은 라이선스")
    # (좌석/디바이스 바인딩 검증 — 기존 bind 로직 재사용)
    sub = db.scalar(select(Subscription).where(Subscription.user_id == lic.user_id)
                    .order_by(Subscription.id.desc()))
    expiry = sub.current_period_end if (sub and sub.status == "active") else lic.expires_at
    from app.services.license_file import issue_license_file
    lf = issue_license_file(settings.license_private_key, license_key=lic.license_key,
                            plan=lic.user.plan, device_fingerprint=body.deviceFingerprint,
                            expiry=expiry, seats=lic.seats)
    return {"licenseFile": lf, "expiry": expiry}
```
> `config.py`에 `license_private_key: str` 추가 (env `SMARTPLACE_LICENSE_PRIVATE_KEY`).

### (D) 데스크톱: 오프라인 검증 — `desktop/license.py` (신규)
```python
import base64, json
from datetime import datetime, timezone
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.exceptions import InvalidSignature

PUBLIC_KEY_HEX = "여기에_공개키_hex_박기"        # (A)에서 출력된 공개키
SIGN_PREFIX = b"license/"                          # 서명 측과 반드시 동일
LICENSE_CACHE = Path.home() / ".smartplace_beta" / "license.lic"

def verify_license_file(license_file: str, device_fingerprint: str) -> dict:
    body = (license_file.replace("-----BEGIN LICENSE FILE-----", "")
                        .replace("-----END LICENSE FILE-----", "").strip())
    env = json.loads(base64.b64decode(body))
    if env.get("alg") != "ed25519":
        raise ValueError("지원하지 않는 알고리즘")
    data_b64, sig_b64 = env["data"], env["sig"]

    pub = Ed25519PublicKey.from_public_bytes(bytes.fromhex(PUBLIC_KEY_HEX))
    try:
        pub.verify(base64.b64decode(sig_b64), SIGN_PREFIX + data_b64.encode())
    except InvalidSignature:
        raise ValueError("서명 검증 실패 — 위변조된 라이선스")

    p = json.loads(base64.b64decode(data_b64))
    now = datetime.now(timezone.utc)
    if p["deviceFingerprint"] != device_fingerprint:
        raise ValueError("다른 기기에서 발급된 라이선스입니다")
    if datetime.fromisoformat(p["issued"]) > now:
        raise ValueError("발급일이 미래 — 시계 확인")
    if datetime.fromisoformat(p["expiry"]) < now:
        raise ValueError("구독이 만료되었습니다")
    return p

def cache_license(license_file: str) -> None:
    LICENSE_CACHE.parent.mkdir(parents=True, exist_ok=True)
    LICENSE_CACHE.write_text(license_file)

def load_cached_license() -> str | None:
    return LICENSE_CACHE.read_text() if LICENSE_CACHE.exists() else None
```

### (E) 데스크톱: 부팅 시 게이트 (앱 진입 전)
```python
# app.py 또는 automation 진입 전
# 1) 온라인이면: /license/activate 호출 → 새 라이선스 파일 받아 cache_license()
# 2) 오프라인이면: load_cached_license() 사용
# 3) verify_license_file(lf, device_fp) 성공해야 기능 활성화. 실패 시 "구독/로그인 필요" 화면.
```

## 4. 결제(구독) 연결 — 이미 있는 billing 재사용
- `app/billing/provider.py`의 Mock을 **LemonSqueezy / Stripe / Toss**로 교체 (인터페이스 동일).
  - 소프트웨어 판매는 **LemonSqueezy** 추천(= Merchant of Record, 부가세·환불 대행 + 라이선스키 기능 내장). 해외 판매 시 세금 처리가 큼.
- `routers/billing.py::webhook`에서 결제 성공 시:
  - `subscription.status = "active"`, `subscription.current_period_end = (다음 결제일)`
  - 구독 취소 webhook → `status="canceled"` → 다음 발급부터 `expiry`가 갱신 안 됨 → 앱이 자연 만료.
- 앱은 **실행할 때마다(온라인일 때) `/license/activate` 재호출** → 최신 `expiry` 반영. 오프라인이면 캐시로 버팀.

## 5. 함정(gotcha) — 소스에서 확인한 것

- ⚠️ **서명 메시지 접두사.** Keygen은 `machine/<enc>` 를 서명함(`Buffer.from('machine/'+msg)`). 우리도 `b"license/"+data_b64` 처럼 **서명·검증 양쪽 접두사가 1바이트라도 다르면 무조건 실패**. 가장 흔한 버그.
- ⚠️ **이중 base64.** 봉투(envelope)도 base64(JSON), 그 안 `data`도 base64(JSON). **서명은 `data`의 base64 문자열에 대해** 한다(디코드한 JSON이 아니라). Keygen `verify(publicKey, enc, sig)`에서 `enc`(인코딩된 문자열)에 서명/검증함.
- ⚠️ **개인키는 절대 앱에 넣지 말 것.** 앱엔 공개키만. (HMAC에서 못 벗어나면 이 전체가 무의미)
- ⚠️ **만료 검사 양방향.** `issued > now`(미래 발급=시계 조작 의심)와 `expiry < now` 둘 다 확인. (소스에 그대로 있음)
- ⚠️ **시계 되돌리기(offline 한계).** 사용자가 PC 시계를 과거로 돌리면 만료 우회 가능. 완화: 온라인 갱신 때 마지막 검증시각 저장 → 시계가 그보다 과거면 거부. (Keygen은 온라인 heartbeat로 처리. 완전 차단은 불가 — 알고 갈 것.)
- ⚠️ **기기 핑거프린트 안정성.** 재부팅·업데이트에도 동일해야 함(해시 입력에 휘발 값 넣지 말 것). `cloud/backend` 디바이스 바인딩과 동일 규칙 사용.
- ⚠️ **암호화 변형 쓸 경우** AES-256-GCM은 `setAuthTag`와 빈 AAD까지 정확히 맞춰야 함(소스 `setAAD(Buffer.from(''))`). MVP는 서명만으로 가서 이 복잡도 회피 권장.

## 6. 실행 순서 체크리스트
- [ ] `cryptography` 의존성 확인 (cloud·desktop 둘 다 이미 사용 중)
- [ ] `scripts/gen_license_keys.py` 실행 → 개인키는 서버 `.env`(`SMARTPLACE_LICENSE_PRIVATE_KEY`), 공개키는 `desktop/license.py` 상수에
- [ ] `cloud/backend/app/core/config.py`에 `license_private_key` 추가
- [ ] `app/services/license_file.py` 작성 (B)
- [ ] `routers/license.py`에 `POST /license/activate` 추가 (C)
- [ ] `desktop/license.py` 작성 (D) + 부팅 게이트 (E)
- [ ] `desktop` 기기 핑거프린트 함수 추가(가능하면 `cloud`와 동일 규칙)
- [ ] billing webhook이 `subscription.current_period_end`를 정확히 세팅하는지 확인
- [ ] 결제 프로바이더 선택(LemonSqueezy 권장) → `provider.py` 어댑터 구현
- [ ] 만료/위조/다른기기/오프라인 4가지 시나리오 테스트
- [ ] (선택) 시계 되돌리기 완화 로직

## 7. 참고한 레퍼런스 실제 파일
- `keygen-sh/air-gapped-activation-example` (MIT)
  - `client/components/steps/Verify.tsx` — Ed25519 검증 + AES-256-GCM 복호화 + 만료 검사 (핵심)
  - `client/components/steps/Upload.tsx` — `-----BEGIN MACHINE FILE-----` 파일 포맷
- Keygen 공식 문서: https://keygen.sh/docs/choosing-a-licensing-model/offline-licenses/
- 결제(소프트웨어 판매): LemonSqueezy(라이선스키+구독 내장, MoR) / Stripe / Toss

---
*이 문서는 청사진입니다. 실제 구현은 별도 단계로, 승인 후 진행합니다.*
