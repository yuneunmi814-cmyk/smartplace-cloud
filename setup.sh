#!/bin/bash
# 게이트웨이(네이버 자동화) 자동 설치. 터미널에서 `bash setup.sh` 로 실행.
set -e
cd "$(dirname "$0")/gateway"

echo "=========================================="
echo " 79대포 사진등록 프로그램 설치를 시작합니다"
echo " (몇 분 걸려요. 끝날 때까지 기다리세요)"
echo "=========================================="

python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip >/dev/null
pip install -r requirements-dev.txt
playwright install chromium

echo ""
echo "=========================================="
echo " ✅ 설치 완료!"
echo " 이제 가이드의 '3단계'부터 따라 하세요."
echo "=========================================="
