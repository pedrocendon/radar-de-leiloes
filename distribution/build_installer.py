"""Reproducible payload preparation. Run from the delivery workspace root.

Inputs in work/installer-downloads: official Python 3.13.16 embed amd64 ZIP,
SQLite 3.54.1 x64 DLL and XlsxWriter 3.2.9 wheel. Compile radar.iss afterward.
"""
import hashlib
import json
import shutil
import subprocess
import zipfile
from pathlib import Path
from PIL import Image,ImageDraw

ROOT=Path(__file__).resolve().parent.parent
SOURCE=ROOT
DIST=SOURCE/'distribution'
BUILD=ROOT/'work/installer-build'
PAYLOAD=BUILD/'payload'
DOWNLOAD=ROOT/'work/installer-downloads'
EXPECTED='97dae5274cc54867065e8d5a3226e48c35017ed332a0fdb0e27d5b5821961297'
def verify_input(name, expected):
    if hashlib.sha256((DOWNLOAD/name).read_bytes()).hexdigest()!=expected:
        raise ValueError('SHA-256 divergente: '+name)

verify_input('python.zip', EXPECTED)
verify_input('xlsxwriter-3.2.9-py3-none-any.whl', '9a5db42bc5dff014806c58a20b9eae7322a134abb6fce3c92c181bfb275ec5b3')
verify_input('webview2.nupkg', '56f7f4b8bf9aee4b8efefbbdd4f67d5f74ebd1b100ed0806da71bf76af481aa9')
verify_input('MicrosoftEdgeWebview2Setup.exe', 'aa38a8cfce6179b87181609b1c730a29eaf26138fc833af5759e67576770f3a3')
sqlite_archive=DOWNLOAD/'sqlite-dll-win-x64-3540100.zip'
if hashlib.sha3_256(sqlite_archive.read_bytes()).hexdigest()!='c2d09c8babb9399277055c057c97a53f1ffd7c5f11d0c1f2118ffdfa39f2daa4':
    raise ValueError('SHA3-256 divergente: SQLite 3.54.1')
for part in ['runtime','app/defaults','app/ui','licenses']:(PAYLOAD/part).mkdir(parents=True,exist_ok=True)
with zipfile.ZipFile(DOWNLOAD/'python.zip') as archive:archive.extractall(PAYLOAD/'runtime')
with zipfile.ZipFile(sqlite_archive) as archive:
    (PAYLOAD/'runtime/sqlite3.dll').write_bytes(archive.read('sqlite3.dll'))
with zipfile.ZipFile(DOWNLOAD/'xlsxwriter-3.2.9-py3-none-any.whl') as archive:archive.extractall(PAYLOAD/'runtime/Lib/site-packages')
with zipfile.ZipFile(DOWNLOAD/'webview2.nupkg') as archive:
    for name in ['Microsoft.Web.WebView2.Core.dll','Microsoft.Web.WebView2.WinForms.dll']:
        (PAYLOAD/name).write_bytes(archive.read('lib/net462/'+name))
    (PAYLOAD/'WebView2Loader.dll').write_bytes(archive.read('runtimes/win-x64/native/WebView2Loader.dll'))
    (PAYLOAD/'licenses/WebView2.txt').write_bytes(archive.read('LICENSE.txt'))
(PAYLOAD/'runtime/python313._pth').write_text('python313.zip\n.\n../app\nLib/site-packages\n',encoding='utf-8')
sqlite_version=subprocess.check_output([str(PAYLOAD/'runtime/python.exe'),'-c','import sqlite3;print(sqlite3.sqlite_version)'],text=True).strip()
if sqlite_version!='3.54.1':raise RuntimeError('A compilação não carregou o SQLite corrigido.')
for name in ['app.py','collectors.py','engine.py','friendly_ui.py','xlsx_export.py','portable_excel.py','updater.py','version.py','startup.py','notifications.py','favorite_notifications.py','favorite_changes.py']:
    shutil.copy2(SOURCE/name,PAYLOAD/'app'/name)
shutil.copy2(DIST/'desktop.py',PAYLOAD/'app/desktop.py')
for name in ['ui.js','index.html','style.css']:
    content=(SOURCE/'ui'/name).read_text(encoding='utf-8')
    content=content.replace('ABRIR RADAR.vbs','Radar de Leilões na área de trabalho')
    content=content.replace('Dê dois cliques em Radar de Leilões na área de trabalho. Se o Windows não executar esse arquivo, use INICIAR.cmd. O programa abre no seu navegador e usa os dados desta pasta.', 'Dê dois cliques no ícone Radar de Leilões na área de trabalho ou no menu Iniciar. Seus anúncios ficam salvos neste computador.')
    content=content.replace('Sugestão baseada na sua planilha original.','Sugestão inicial de busca.')
    content=content.replace('Sim. As consultas em andamento continuam. Para encerrar também a repetição automática, clique em Encerrar programa. Seus dados ficam salvos.', 'Sim. O Radar continua no ícone perto do relógio do Windows, mesmo com o navegador fechado. Clique com o botão direito no ícone para ver a próxima busca, abrir o programa, pausar a agenda ou encerrar. Se o ícone estiver oculto, procure na seta ao lado do relógio. Seus dados ficam salvos.')
    content=content.replace('Você pode começar com os imóveis da sua planilha original.','Escolha suas preferências e clique em Buscar novidades.')
    content=content.replace('A geração depende dos componentes disponíveis neste computador; em outro computador pode ser necessária configuração adicional.','O instalador inclui o gerador da planilha. Para abrir o arquivo, use Excel ou outro aplicativo compatível.')
    content=content.replace('Posso fechar o navegador?', 'Posso fechar a janela?')
    content=content.replace('mesmo com o navegador fechado', 'mesmo com a janela fechada')
    content=content.replace('Fechar a aba não encerra o programa', 'Fechar a janela mantém o Radar em segundo plano')
    content=content.replace('Cópia enviada para os downloads do navegador.', 'Escolha onde salvar a cópia na janela que será aberta.')
    content=content.replace('Você pode fechar esta aba.', 'A janela será fechada em instantes.')
    (PAYLOAD/'app/ui'/name).write_text(content,encoding='utf-8')
config=json.loads((SOURCE/'config.example.json').read_text(encoding='utf-8'))
config['profile']={'cities':[],'note':'Instalação nova. Configure sua busca em Minha busca.'}
config['suggested_filters']=dict(config['filters'],types=['apartamento'])
config['property_overrides']={}
for source in config['sources']:source['watch_urls']=[]
(PAYLOAD/'app/defaults/config.json').write_text(json.dumps(config,ensure_ascii=False,indent=2),encoding='utf-8')
(PAYLOAD/'app/defaults/references.json').write_text('[]',encoding='utf-8')
shutil.copy2(DIST/'COMO-USAR.txt',PAYLOAD/'COMO-USAR.txt')
shutil.copy2(PAYLOAD/'runtime/LICENSE.txt',PAYLOAD/'licenses/Python.txt')
license_file=next((PAYLOAD/'runtime/Lib/site-packages').glob('xlsxwriter-*.dist-info/LICENSE.txt'))
shutil.copy2(license_file,PAYLOAD/'licenses/XlsxWriter.txt')
(PAYLOAD/'licenses/SQLite.txt').write_text('SQLite 3.54.1 is in the public domain.\nhttps://sqlite.org/copyright.html\nOfficial Windows x64 binary: https://sqlite.org/2026/sqlite-dll-win-x64-3540100.zip\n',encoding='utf-8')
(PAYLOAD/'licenses/COMPONENTES.txt').write_text('Python 3.13.16: https://www.python.org/ftp/python/3.13.16/python-3.13.16-embed-amd64.zip\nXlsxWriter 3.2.9: https://pypi.org/project/XlsxWriter/3.2.9/\nDados de cidades e estados: API pública IBGE, consulta em 02/10/2026.\nhttps://servicodados.ibge.gov.br/api/v1/localidades/municipios\n',encoding='utf-8')
image=Image.new('RGBA',(256,256),(0,0,0,0));draw=ImageDraw.Draw(image)
draw.rounded_rectangle((4,4,252,252),radius=52,fill='#203E60')
draw.ellipse((35,35,221,221),outline='#7099C4',width=7)
draw.ellipse((63,63,193,193),outline='#406991',width=4)
draw.line((128,128,196,60),fill='#59C5AB',width=9)
draw.polygon([(74,132),(128,87),(182,132),(169,147),(128,113),(87,147)],fill='white')
draw.rounded_rectangle((92,135,164,192),radius=5,fill='white')
draw.rectangle((119,156,139,194),fill='#203E60')
draw.ellipse((186,51,207,72),fill='#59C5AB')
image.save(PAYLOAD/'radar.ico',sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])
csc=Path('C:/Windows/Microsoft.NET/Framework64/v4.0.30319/csc.exe')
subprocess.run([str(csc),'/nologo','/target:winexe','/platform:anycpu','/optimize+',f'/win32icon:{PAYLOAD / "radar.ico"}',f'/out:{PAYLOAD / "Radar.exe"}','/reference:System.Windows.Forms.dll',str(DIST/'Launcher.cs')],check=True)
subprocess.run([str(csc),'/nologo','/target:winexe','/platform:x64','/optimize+',f'/win32icon:{PAYLOAD / "radar.ico"}',f'/out:{PAYLOAD / "RadarTray.exe"}','/reference:System.Windows.Forms.dll','/reference:System.Drawing.dll','/reference:System.Web.Extensions.dll',f'/reference:{PAYLOAD / "Microsoft.Web.WebView2.Core.dll"}',f'/reference:{PAYLOAD / "Microsoft.Web.WebView2.WinForms.dll"}',str(DIST/'Tray.cs'),str(DIST/'RadarWindow.cs')],check=True)
subprocess.run([str(csc),'/nologo','/target:winexe','/platform:x64','/optimize+',f'/win32icon:{PAYLOAD / "radar.ico"}',f'/out:{PAYLOAD / "RadarUpdate.exe"}','/reference:System.Windows.Forms.dll','/reference:System.Web.Extensions.dll',str(DIST/'Updater.cs')],check=True)
manifest={str(p.relative_to(PAYLOAD)):hashlib.sha256(p.read_bytes()).hexdigest() for p in PAYLOAD.rglob('*') if p.is_file()}
(BUILD/'payload-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
print(json.dumps({'files':len(manifest),'payload':str(PAYLOAD),'bytes':sum(p.stat().st_size for p in PAYLOAD.rglob('*') if p.is_file())}))
