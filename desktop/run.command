#!/bin/bash
# 더블클릭으로 베타 앱 실행 (Mac). 처음엔 setup이 자동으로 돕니다.
cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
  echo "처음 실행 — 설치 중 (몇 분 걸려요)..."
  python3 -m venv .venv
  source .venv/bin/activate
  pip install --upgrade pip >/dev/null
  pip install -r requirements.txt
  playwright install chromium
else
  source .venv/bin/activate
fi

echo "앱을 시작합니다..."
python app.py
