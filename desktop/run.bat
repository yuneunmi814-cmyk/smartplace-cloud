@echo off
chcp 65001 >nul
cd /d "%~dp0"

if not exist ".venv" (
  echo ==========================================
  echo  처음 실행 - 설치 중 ^(5~10분 걸려요^)...
  echo  끝날 때까지 기다리세요.
  echo ==========================================
  python -m venv .venv
  call .venv\Scripts\activate.bat
  python -m pip install --upgrade pip
  pip install -r requirements.txt
  playwright install chromium
) else (
  call .venv\Scripts\activate.bat
)

echo.
echo 앱을 시작합니다...
python app.py

echo.
echo 앱이 종료되었습니다. 이 창은 닫아도 돼요.
pause
