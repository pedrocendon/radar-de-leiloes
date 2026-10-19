@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv-web\Scripts\python.exe" (
  py -3 -m venv .venv-web
  if errorlevel 1 goto :error
)
".venv-web\Scripts\python.exe" -c "from importlib.metadata import version; import sys; sys.exit(tuple(int(x) for x in version('pip').split('.')[:2]) < (26,2))" >nul 2>&1
if errorlevel 1 (
  ".venv-web\Scripts\python.exe" -m pip --isolated --disable-pip-version-check install --only-binary=:all: --index-url https://pypi.org/simple pip==26.2
  if errorlevel 1 goto :error
)
".venv-web\Scripts\python.exe" -c "from importlib.metadata import version; import sys; sys.exit(any(version(n)!=v for n,v in [('Flask','3.1.3'),('Werkzeug','3.1.9'),('waitress','3.0.2'),('XlsxWriter','3.2.9')]))" >nul 2>&1
if errorlevel 1 (
  ".venv-web\Scripts\python.exe" -m pip --isolated --disable-pip-version-check install --only-binary=:all: --index-url https://pypi.org/simple -r requirements-web.txt
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
