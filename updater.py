"""Updates from the project's public GitHub releases. Never accepts a URL from the UI."""
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import threading
import time
import urllib.request
import uuid
import zipfile
from contextlib import closing
from pathlib import Path
from urllib.parse import urlsplit
from version import VERSION

REPO = 'pedrocendon/radar-de-leiloes'
API = 'https://api.github.com/repos/' + REPO + '/releases/latest'
MAX_SIZE = 200 * 1024 * 1024


def version_tuple(value):
    if not isinstance(value, str) or not re.fullmatch(r'(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)', value):
        raise ValueError('Versão publicada inválida.')
    return tuple(map(int, value.split('.')))


def release_candidate(data, current=VERSION):
    if data.get('draft') is not False or data.get('prerelease') is not False:
        raise ValueError('A versão publicada ainda não é estável.')
    tag = data.get('tag_name', '')
    version = tag.removeprefix('v')
    number = version_tuple(version)
    if tag != 'v' + version:
        raise ValueError('Identificação da versão inválida.')
    if number <= version_tuple(current):
        return None
    # Accept the existing short filename and the new three-component convention.
    names = {f'Instalar-Radar-de-Leiloes-{version}-Windows.exe'}
    if number[2] == 0:
        names.add(f'Instalar-Radar-de-Leiloes-{number[0]}.{number[1]}-Windows.exe')
    assets = [a for a in data.get('assets', []) if a.get('name') in names]
    if len(assets) != 1:
        raise ValueError('A publicação não contém um único instalador compatível.')
    asset = assets[0]
    digest = asset.get('digest', '')
    size = asset.get('size')
    expected_url = f'https://github.com/{REPO}/releases/download/{tag}/{asset["name"]}'
    if asset.get('state') != 'uploaded' or asset.get('browser_download_url') != expected_url:
        raise ValueError('Origem do instalador não reconhecida.')
    if not re.fullmatch(r'sha256:[a-fA-F0-9]{64}', digest):
        raise ValueError('O GitHub não informou a verificação de integridade do instalador.')
    if type(size) is not int or not 0 < size <= MAX_SIZE:
        raise ValueError('Tamanho do instalador inválido.')
    return dict(version=version, url=expected_url, name=asset['name'], size=size,
                sha256=digest[7:].lower(), notes=str(data.get('body') or '')[:12000])


def allowed_url(url):
    p = urlsplit(url)
    return (p.scheme == 'https' and not p.username and not p.password
            and p.port in (None, 443) and not p.fragment
            and p.hostname in ('api.github.com', 'github.com', 'release-assets.githubusercontent.com', 'objects.githubusercontent.com'))


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        if not allowed_url(newurl):
            raise ValueError('O download foi redirecionado para uma origem não permitida.')
        return super().redirect_request(request, fp, code, msg, headers, newurl)


def open_url(url):
    if not allowed_url(url):
        raise ValueError('Endereço de atualização não permitido.')
    request = urllib.request.Request(url, headers={
        'User-Agent': 'Radar-de-Leiloes/' + VERSION,
        'Accept': 'application/vnd.github+json' if url == API else 'application/octet-stream',
    })
    return urllib.request.build_opener(SafeRedirect()).open(request, timeout=30)


def download(candidate, folder, progress, opener=open_url):
    partial = folder / 'instalador.part'
    target = folder / 'instalador.exe'
    digest = hashlib.sha256()
    total = 0
    started = time.monotonic()
    try:
        with opener(candidate['url']) as response, partial.open('wb') as output:
            while True:
                chunk = response.read(128 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > candidate['size'] or time.monotonic() - started > 900:
                    raise ValueError('O download excedeu o tamanho ou o tempo permitido.')
                output.write(chunk)
                digest.update(chunk)
                progress(total * 100 // candidate['size'])
        if total != candidate['size'] or digest.hexdigest() != candidate['sha256']:
            raise ValueError('O instalador recebido está incompleto ou diferente do publicado. Tente novamente.')
        partial.replace(target)
        return target
    finally:
        partial.unlink(missing_ok=True)


def backup_data(base, destination):
    """Snapshot SQLite through its backup API, then archive user settings, excluding session tokens."""
    from engine import connect_database
    db_copy = destination.with_suffix('.sqlite')
    try:
        with closing(connect_database(base / 'data/monitor.sqlite')) as source, closing(connect_database(db_copy)) as target:
            source.backup(target)
        with zipfile.ZipFile(destination, 'w', zipfile.ZIP_DEFLATED) as archive:
            archive.write(db_copy, 'data/monitor.sqlite')
            for name in ('config.json', 'references.json', 'data/preferencias.json', 'data/atualizacoes.json'):
                if (base / name).is_file():
                    archive.write(base / name, name)
    finally:
        db_copy.unlink(missing_ok=True)


class Updater:
    def __init__(self, service, install_dir, shutdown):
        self.service, self.install_dir, self.shutdown = service, Path(install_dir).resolve(), shutdown
        self.folder = service.base / 'updates'
        self.folder.mkdir(exist_ok=True)
        self.settings = service.base / 'data/atualizacoes.json'
        try:
            prefs = json.loads(self.settings.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            prefs = {}
        self.last_attempt = prefs.get('last_attempt', 0)
        if not isinstance(self.last_attempt, (int, float)):
            self.last_attempt = 0
        self.release = None
        self.data = dict(supported=True, current_version=VERSION, status='idle',
                         automatic=prefs.get('automatic', True) is True, latest_version=None,
                         checked_at=None, percent=0, notes='', message='O Radar verifica novas versões uma vez por dia enquanto está aberto.')
        try:
            receipt = json.loads((self.folder / 'resultado.json').read_text(encoding='utf-8-sig'))
            self.data['last_install'] = receipt.get('message', '')
        except (OSError, ValueError):
            pass

    def state(self):
        with self.service.guard:
            return dict(self.data)

    def save_preferences(self):
        temp = self.settings.with_suffix('.tmp')
        temp.write_text(json.dumps(dict(automatic=self.data['automatic'], last_attempt=self.last_attempt)), encoding='utf-8')
        temp.replace(self.settings)

    def configure(self, payload):
        if type(payload.get('automatic')) is not bool:
            raise ValueError('Escolha se deseja verificar novas versões automaticamente.')
        self.data['automatic'] = payload['automatic']
        self.save_preferences()

    def check(self):
        with self.service.guard:
            if self.data['status'] in ('checking', 'downloading', 'installing'):
                return
            if time.time() - self.last_attempt < 60:
                raise ValueError('Aguarde um minuto antes de verificar novamente.')
            self.data.update(status='checking', message='Verificando novas versões…')
            self.last_attempt = time.time()
            self.save_preferences()
        threading.Thread(target=self._check, daemon=True).start()

    def _check(self):
        try:
            with open_url(API) as response:
                raw = response.read(1024 * 1024 + 1)
            if len(raw) > 1024 * 1024:
                raise ValueError('Resposta de atualização muito grande.')
            candidate = release_candidate(json.loads(raw))
            with self.service.guard:
                self.release = candidate
                self.data.update(status='available' if candidate else 'current', checked_at=time.time(),
                                 latest_version=candidate['version'] if candidate else None,
                                 notes=candidate['notes'] if candidate else '',
                                 message='Uma nova versão está pronta para instalar.' if candidate else 'Você já está usando a versão mais recente disponível para este Radar.')
        except Exception:
            self.service.record_error()
            with self.service.guard:
                self.release = None
                self.data.update(status='error', latest_version=None, message='Não foi possível verificar as versões. Confira a internet e tente novamente. O Radar continua funcionando.')

    def agenda(self):
        startup = True
        while not self.service.closed.wait(20):
            with self.service.guard:
                if self.data['automatic'] and not self.service.job['busy'] and time.time() - self.last_attempt >= (60 if startup else 86400):
                    self.check()
                    startup = False

    def install(self):
        # Called while holding the same lock as searches and all user mutations.
        if self.service.job['busy']:
            raise ValueError('Aguarde a busca ou a planilha terminar antes de instalar.')
        if self.data['status'] != 'available' or not self.release:
            raise ValueError('Verifique as atualizações antes de instalar.')
        candidate = dict(self.release)
        self.data.update(status='downloading', percent=0, message='Baixando a nova versão…')
        self.service.job = dict(busy=True, message='Baixando a nova versão do Radar…', started=time.time(), kind='software', error=False)
        threading.Thread(target=self._install, args=(candidate,), daemon=True).start()

    def _install(self, candidate):
        try:
            folder = self.folder / uuid.uuid4().hex
            folder.mkdir()
            def progress(value):
                with self.service.guard:
                    self.data['percent'] = value
            installer = download(candidate, folder, progress)
            with self.service.guard:
                self.data.update(message='Preparando a cópia de segurança dos seus dados…')
            backup_data(self.service.base, folder / 'dados-antes-da-atualizacao.zip')
            helper = folder / 'RadarUpdate.exe'
            shutil.copy2(self.install_dir / 'RadarUpdate.exe', helper)
            args = [str(helper), str(os.getpid()), str(installer), candidate['sha256'],
                    str(self.install_dir), candidate['version'], str(self.folder / 'resultado.json')]
            process = subprocess.Popen(args, creationflags=subprocess.CREATE_NO_WINDOW)
            ready = folder / 'pronto.txt'
            for _ in range(100):
                if ready.exists():
                    break
                if process.poll() is not None:
                    raise RuntimeError('O auxiliar de atualização não iniciou.')
                time.sleep(.1)
            else:
                process.terminate()
                raise RuntimeError('O auxiliar de atualização não respondeu.')
            with self.service.guard:
                self.data.update(status='installing', message='Instalando. O Radar fechará e abrirá novamente em instantes…')
                self.service.job['message'] = self.data['message']
            time.sleep(2)  # Give the visible UI a chance to show the restart message.
            self.service.closed.set()
            self.shutdown()
        except Exception:
            self.service.record_error()
            with self.service.guard:
                self.data.update(status='available', message='Não foi possível instalar. Seus dados foram mantidos. Tente novamente; se continuar, consulte Ajuda.')
                self.service.job.update(busy=False, error=True, message='A atualização do programa não foi concluída. Você pode continuar usando o Radar.')
