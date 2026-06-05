#!/bin/bash
# 전체 설치(백엔드+게이트웨이+웹). 터미널에서 `bash setup.sh` 로 실행.
# 미리 Python 3.12+ 와 Node 20+ 가 설치돼 있어야 합니다.
set -e
cd "$(dirname "$0")"

echo "=============================================="
echo " 79대포 사진관리 프로그램 설치를 시작합니다"
echo " (5~10분 걸려요. 끝날 때까지 기다리세요)"
echo "=============================================="

echo ""
echo "[1/3] 백엔드 설치 중..."
( cd backend && python3 -m venv .venv && source .venv/bin/activate && pip install --upgrade pip >/dev/null && pip install -r requirements-dev.txt >/dev/null )

echo "[2/3] 게이트웨이(네이버 자동화) 설치 중..."
( cd gateway && python3 -m venv .venv && source .venv/bin/activate && pip install --upgrade pip >/dev/null && pip install -r requirements-dev.txt >/dev/null && playwright install chromium )

echo "[3/3] 웹 설치 중..."
( cd web && npm install >/dev/null 2>&1 )

echo ""
echo "=============================================="
echo " ✅ 설치 완료!"
echo " 이제 가이드의 다음 단계(.env 넣기 → 네이버 로그인)를 하세요."
echo "=============================================="
