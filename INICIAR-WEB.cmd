@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv-web\Scripts\python.exe" (
  py -3 -m venv .venv-web
  if errorlevel 1 goto :error
  ".venv-web\Scripts\python.exe" -m pip install -r requirements-web.txt
  if errorlevel 1 goto :error
)
echo Radar web: http://127.0.0.1:8080
echo Para criar o primeiro acesso, use CRIAR-CONVITE-WEB.cmd em outra janela.
echo Fechar esta janela interrompe o servidor local. Dados ficam em web-data.
".venv-web\Scripts\python.exe" -m web.server
if errorlevel 1 goto :error
exit /b 0
:error
echo Nao foi possivel iniciar. Instale Python 3.12 ou 3.13 e consulte docs\WEB.md.
pause
exit /b 1
