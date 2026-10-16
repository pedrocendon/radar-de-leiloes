@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv-web\Scripts\python.exe" (
  echo Abra INICIAR-WEB.cmd primeiro.
  pause
  exit /b 1
)
".venv-web\Scripts\python.exe" -c "import subprocess,sys; email=input('E-mail de quem vai usar o Radar: ').strip(); sys.exit(subprocess.call([sys.executable,'-m','web.manage','invite',email]))"
pause
