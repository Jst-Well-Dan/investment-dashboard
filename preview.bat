@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 本地预览：http://127.0.0.1:8080/
start "" http://127.0.0.1:8080/
python -m http.server 8080 --directory docs
