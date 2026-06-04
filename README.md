# SmartPlace Cloud

네이버 스마트플레이스 **다계정 통합 이미지 관리 자동화** 솔루션 (기업용, Cloud-First).

> 기획서 `네이버 스마트플레이스 통합 이미지 관리 자동화 솔루션 기획서` 기준 구현.
> 로컬 PC의 대표 이미지를 **여러 가맹점에 일괄 배포**하고, 작업을 예약·모니터링합니다.

## 아키텍처

```
React (Vite)  →  FastAPI  →  PostgreSQL
                    │   └────→  AWS S3 (이미지)
                    └────────→  Redis (작업 큐)  →  Worker  →  Naver API Gateway
```

- **포트 & 어댑터**: S3/Redis/Naver는 실제 어댑터(boto3·redis-py·httpx)로 구현하되 인터페이스로 분리 → 테스트는 in-memory fake로 검증, 운영은 실서비스. (`app/services/`)
- **Retry Policy**: 워커가 가맹점별로 `task_max_retries`회 선형 백오프 재시도 후 실패 처리. (`app/worker/processor.py`)
- **Audit Trail**: 모든 민감 동작(계정 연동·배포·승인…)을 append-only 로그로 기록. (`app/services/audit.py`)
- **RBAC**: `admin` / `user` 역할, 가입은 승인 대기(pending) → 관리자 승인. 첫 가입자는 자동 admin.

## 빠른 시작

### 옵션 A — docker compose (Postgres + Redis + API + Worker)

```bash
cp backend/.env.example backend/.env     # 필요 시 시크릿/AWS/네이버 키 입력
docker compose up --build                # API :8000
```

### 옵션 B — 로컬 개발 (SQLite, 외부 서비스 없이)

```bash
# 1) 백엔드
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload            # http://localhost:8000/docs

# 2) 워커 (실제 큐 처리 시 Redis 필요)
python -m app.worker.worker

# 3) 웹
cd ../web && npm install && npm run dev   # http://localhost:5173
```

> 로컬 SQLite 모드에서는 S3/Redis/Naver 호출이 실제로 일어납니다(설정된 경우). 키가 없으면 이미지 업로드·배포 단계에서 외부 호출이 실패하므로, 무키 로컬 테스트는 `pytest`(in-memory fake)를 사용하세요.

## 사용자 흐름

1. **로그인/가입** — 첫 가입자=admin(승인됨), 이후=pending(관리자 승인 필요)
2. **계정 연동** — 네이버 토큰 입력 → **AES-256-GCM 암호화** 저장
3. **가맹점 등록** — 연동 계정 아래 Place 등록
4. **이미지 업로드** — S3 저장
5. **배포** — 이미지 + 가맹점 다중선택 → 즉시/예약 → Redis 큐 → Worker가 Naver Gateway로 적용
6. **작업 현황** — 진행률·성공/실패·재시도 결과, 예약/큐 상태 취소

## API 요약

| 기능 | 메서드 | Endpoint |
|---|---|---|
| 회원가입/로그인/갱신/내정보 | POST/GET | `/api/v1/auth/*` |
| 네이버 계정 연동·목록·해제 | POST/GET/DELETE | `/api/v1/naver-accounts` |
| 가맹점 등록·목록 | POST/GET | `/api/v1/places` |
| 이미지 업로드·목록 | POST/GET | `/api/v1/images` |
| 배포·조회·취소 | POST/GET/PATCH | `/api/v1/tasks` |
| 사용자/승인/역할·감사·통계 | GET/POST/PATCH | `/api/v1/admin/*` |

전체 문서: http://localhost:8000/docs

## 보안 (기획서 1-4)

| 항목 | 구현 |
|---|---|
| 인증/인가 | JWT(Access 15m + Refresh), 모든 요청 헤더 검증, RBAC |
| 데이터 보안 | 네이버 토큰 **AES-256-GCM**(`core/crypto.py`), 비밀번호 **Bcrypt(cost 12)** |
| SQL Injection | SQLAlchemy 파라미터 바인딩 |
| XSS | React 기본 이스케이프, 사용자 입력 비-HTML 렌더 |
| 감사 | append-only AuditLog |

## 테스트 · CI

```bash
cd backend && source .venv/bin/activate
pip install -r requirements-dev.txt
python -m pytest          # 23 cases
```

- **23 케이스**: 인증/RBAC·암호화·계정/가맹점·이미지·배포(큐)·**워커 재시도/부분성공**·관리자/감사. 외부 서비스는 in-memory fake로 대체.
- **게이트웨이 3 케이스**(mock): 헬스·키 인증·적용 성공.
- **GitHub Actions** [.github/workflows/ci.yml](.github/workflows/ci.yml): 백엔드·게이트웨이 pytest + 웹 typecheck/build.

## 네이버 게이트웨이 (ID/PW 자동화) — `gateway/`

네이버는 공식 API가 없어, 워커가 호출하는 **자동화 마이크로서비스**(`gateway/`)가 실제 웹 UI를 Playwright로 제어합니다.

- 사용자는 웹에서 **네이버 아이디·비밀번호**를 입력 → 백엔드가 **AES-256 암호화** 저장 → 워커가 복호화해 게이트웨이에 전달 → 게이트웨이가 로그인 후 이미지 등록.
- 기본은 `GATEWAY_MOCK=1`(브라우저 없이 200). 실제 자동화는 `GATEWAY_MOCK=0` + `playwright install chromium`.
- ⚠️ ID/PW 로그인은 **캡차·2차 인증**에 막힐 수 있습니다(→ `423` 후 워커 재시도). 권장 운영은 최초 1회 수동 로그인으로 세션 시드. 자세한 내용·셀렉터 튜닝: [gateway/README.md](gateway/README.md).

```
워커 ──HTTP(계약)──▶ gateway ──Playwright──▶ 네이버 스마트플레이스
       Bearer 키          (로그인+사진등록, 세션 캐시)
```

## 실연동 체크리스트 (이 저장소는 구조·어댑터까지 완료)

- **AWS S3**: `.env`에 `SMARTPLACE_AWS_ACCESS_KEY_ID/SECRET`, `S3_BUCKET`, `S3_REGION`
- **Naver Gateway**: `SMARTPLACE_NAVER_GATEWAY_URL/KEY` (기획서의 Naver API Gateway 엔드포인트)
- **PostgreSQL**: `SMARTPLACE_DATABASE_URL` (compose 기본 제공) + 프로덕션은 **Alembic** 마이그레이션 도입
- **시크릿**: `JWT_SECRET`, `DATA_ENCRYPTION_KEY`(`python -c "import secrets;print(secrets.token_hex(32))"`)

> ⚠️ 기획서 조언대로 네이버 정책 변화에 민감합니다. 안정화 단계에서 **예외 처리(Retry)·로그 투명성**을 최우선으로 두었고, 추후 순위 추적/리뷰 관리로 확장 가능합니다.
