@echo off
chcp 65001 >/dev/null
cd /d "%~dp0"
echo === 1/3 构建并检查 ===
python -m sitegen.build
if errorlevel 1 (
  echo.
  echo 构建或检查未通过，已停止发布。
  pause
  exit /b 1
)
echo.
echo === 2/3 提交 ===
git add -A
git commit -m "build: %date% %time%"
if errorlevel 1 echo （没有变更可提交，继续）
echo.
echo === 3/3 推送 ===
git push
if errorlevel 1 (
  echo 推送失败，检查远程与凭证。
  pause
  exit /b 1
)
echo.
echo 已推送。等 GitHub Pages 构建完成即可访问。
pause
