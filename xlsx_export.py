"""Refresh the managed Excel report without risking the last good workbook."""
import json
import os
import subprocess
import tempfile
from pathlib import Path

REPORT_NAME = 'Radar-de-Leiloes.xlsx'


def runtime():
    root = Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/node'
    node = Path(os.environ.get('RADAR_NODE_EXE', str(root/'bin/node.exe')))
    modules = Path(os.environ.get('RADAR_NODE_MODULES', str(root/'node_modules')))
    if not node.is_file() or not (modules/'@oai/artifact-tool/package.json').is_file():
        raise RuntimeError('Gerador Excel indisponível. Configure RADAR_NODE_EXE e RADAR_NODE_MODULES conforme LEIA-ME.txt. CSV e banco continuam disponíveis.')
    return node, modules


def refresh_excel(base, payload):
    base = Path(base).resolve()
    folder = base/'exports'
    folder.mkdir(exist_ok=True)
    report = folder/REPORT_NAME
    status_path = folder/'situacao-planilha.json'
    previous = {}
    if status_path.exists():
        try: previous = json.loads(status_path.read_text(encoding='utf-8'))
        except (ValueError, OSError): pass
    result = {'ultima_tentativa': payload['generated_at'], 'ultima_atualizacao': previous.get('ultima_atualizacao'),
              'situacao': 'pendente', 'arquivo': REPORT_NAME, 'mensagem': ''}
    try:
        # Each export has its own input and output; replacement is atomic.
        with tempfile.TemporaryDirectory(prefix='excel-', dir=base/'data') as temp:
            temp = Path(temp)
            snapshot = temp/'dados.json'
            generated = temp/'painel.xlsx'
            snapshot.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
            if os.environ.get('RADAR_PORTABLE_EXCEL') == '1':
                from portable_excel import build_report
                build_report(payload, generated)
            else:
                node, modules = runtime()
                env = dict(os.environ, RADAR_NODE_MODULES=str(modules))
                proc = subprocess.run([str(node), str(base/'report_builder.mjs'), str(snapshot), str(generated)],
                                      env=env, capture_output=True, text=True, encoding='utf-8', errors='replace',
                                      timeout=240, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                if proc.returncode or not generated.is_file():
                    raise RuntimeError('Não foi possível gerar o Excel: '+(proc.stderr or proc.stdout)[-1800:])
            try:
                generated.replace(report)
            except PermissionError:
                raise RuntimeError('O Excel está aberto ou a pasta está sem permissão. Feche a planilha e execute ATUALIZAR-PLANILHA.cmd. A versão anterior foi preservada.')
        result.update(situacao='atualizada', ultima_atualizacao=payload['generated_at'],
                      mensagem='Planilha atualizada com os dados salvos. Consulte a situação de cada fonte no arquivo.')
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
        result['mensagem'] = str(exc)
    status_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    return result


def status_message(base):
    path = Path(base)/'exports/situacao-planilha.json'
    if not path.exists(): return 'Planilha ainda não gerada.'
    return json.loads(path.read_text(encoding='utf-8'))['mensagem']
