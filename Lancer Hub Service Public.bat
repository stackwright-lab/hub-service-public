@echo off
rem Double-cliquez (Windows) pour ouvrir la page du Hub Service Public dans le navigateur.
cd /d "%~dp0"
uv run hub-web
pause
