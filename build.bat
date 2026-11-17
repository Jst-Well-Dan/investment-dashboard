@echo off
chcp 65001 >/dev/null
cd /d "%~dp0"
python -m sitegen.build
if errorlevel 1 (
  echo.
  echo 构建失败。
  pause
  exit /b 1
)
echo.
echo 本地预览：现在打开 docs\index.html
start "" "docs\index.html"
