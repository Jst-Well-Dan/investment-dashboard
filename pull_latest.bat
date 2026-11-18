@echo off
chcp 65001 >nul
cd /d "%~dp0"
python pull_latest.py %*
if errorlevel 1 (
  echo.
  echo 拉数据失败，research.yaml 没有改动。
  pause
  exit /b 1
)
echo.
echo 接着跑 build.bat 就能看到新卡片。
pause
