@echo off
echo Starting React frontend on http://localhost:5173
cd /d "%~dp0"
call npm install
call npm run dev
