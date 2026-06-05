#!/bin/bash
# 프로그램 시작(서버 3개 한 번에 + 브라우저 자동 열기).
# 터미널에서 `bash start.sh` 로 실행. 끄려면 이 창에서 Control+C.
cd "$(dirname "$0")"
trap 'echo; echo "프로그램을 종료합니다..."; kill 0' EXIT

echo "프로그램을 시작합니다... (이 검은 창은 끄지 마세요!)"

( cd gateway && source .venv/bin/activate && GATEWAY_MOCK=0 GATEWAY_KEY=gateway-key-change-me \
    uvicorn app.main:app --port 8100 >/tmp/spc-gateway.log 2>&1 ) &

( cd backend && source .venv/bin/activate \
    && uvicorn app.main:app --port 8000 >/tmp/spc-backend.log 2>&1 ) &

( cd web && npm run dev >/tmp/spc-web.log 2>&1 ) &

echo "잠시 기다리는 중 (10초)..."
sleep 10
echo "브라우저에서 사이트를 엽니다 → http://localhost:5173"
open http://localhost:5173 2>/dev/null || true
echo ""
echo "✅ 실행 중! 브라우저에서 사용하세요."
echo "   끄려면 이 창에서 Control + C 를 누르세요."
wait
