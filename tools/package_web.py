"""Build a source/runtime ZIP from an explicit allowlist; no account data."""
import hashlib
import zipfile
from pathlib import Path

BASE=Path(__file__).resolve().parent.parent
FILES=['requirements.txt','requirements-web.txt','Dockerfile.web','.dockerignore','compose.web.yml',
       'INICIAR-WEB.cmd','CRIAR-CONVITE-WEB.cmd','LEIA-ME-WEB.txt',
       'collectors.py','engine.py','friendly_ui.py','app.py','notifications.py','favorite_notifications.py',
       'favorite_changes.py','portable_excel.py','xlsx_export.py','version.py','config.example.json',
       'ui/index.html','ui/ui.js','ui/style.css','docs/WEB.md','docs/VALIDACAO-WEB.md','test_web.py',
       'web/__init__.py','web/accounts.py','web/network.py','web/runtime.py','web/server.py','web/manage.py',
       'web/index.html','web/login.html','web/login.js','web/web.js','web/web.css','web/Caddyfile','tools/package_web.py']


def main():
    output=BASE/'dist/Radar-Web.zip';output.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as archive:
        for name in FILES:archive.write(BASE/name,'Radar-Web/'+name)
    with zipfile.ZipFile(output) as archive:
        assert archive.testzip() is None
        assert len(archive.namelist())==len(FILES)
    sha=hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix('.sha256').write_text(sha+'  '+output.name+'\n',encoding='ascii')
    print(str(output));print(str(output.stat().st_size)+' bytes; '+str(len(FILES))+' arquivos');print(sha)


if __name__=='__main__':main()
