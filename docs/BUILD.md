# Gerar o instalador Windows

Use Windows 10 ou 11 de 64 bits, Python 3.13, as dependências de `requirements-dev.txt` e Inno Setup 6, obtido no site oficial https://jrsoftware.org/isinfo.php.

O script usa o compilador C# do .NET Framework em `C:/Windows/Microsoft.NET/Framework64/v4.0.30319/csc.exe`.

## Componentes de entrada

Crie `work/installer-downloads` na raiz do repositório e salve os seguintes arquivos com os nomes indicados:

| Nome local | Origem oficial |
| --- | --- |
| python.zip | https://www.python.org/ftp/python/3.13.16/python-3.13.16-embed-amd64.zip |
| xlsxwriter-3.2.9-py3-none-any.whl | `python -m pip download --no-deps XlsxWriter==3.2.9 -d work/installer-downloads` |
| webview2.nupkg | https://api.nuget.org/v3-flatcontainer/microsoft.web.webview2/1.0.4258.31/microsoft.web.webview2.1.0.4258.31.nupkg |
| MicrosoftEdgeWebview2Setup.exe | https://go.microsoft.com/fwlink/p/?LinkId=2124703 |

O script verifica os hashes de Python, XlsxWriter, WebView2 e do instalador auxiliar. O endereço do instalador auxiliar pode passar a fornecer uma versão nova. Nesse caso, revise sua origem e assinatura Microsoft antes de atualizar o hash esperado. Não desative a verificação.

## Preparar e compilar

Execute na raiz do repositório, em PowerShell:

```powershell
python -m pip install -r requirements-dev.txt
python distribution/build_installer.py
$radarRoot = (Get-Location).Path
& 'C:\Program Files (x86)\Inno Setup 6\ISCC.exe' "/DPayload=$radarRoot\work\installer-build\payload" "/DOutput=$radarRoot\dist" "/DIcon=$radarRoot\work\installer-build\payload\radar.ico" "/DBootstrapper=$radarRoot\work\installer-downloads\MicrosoftEdgeWebview2Setup.exe" distribution/radar.iss
```

Ajuste somente o caminho do Inno Setup se estiver instalado em outro local. O resultado é `dist/Instalar-Radar-de-Leiloes-0.8.2-Windows.exe`.

O instalador inclui Python, o gerador Excel e a janela própria. Usa uma configuração inicial vazia e oferece um atalho na área de trabalho. Quando necessário, instala o WebView2 pela distribuição oficial da Microsoft, com acesso à internet. Os dados do usuário ficam em `%LOCALAPPDATA%\RadarLeiloes`.

Antes de distribuir uma nova compilação, teste instalar, abrir, salvar uma busca, favoritar um anúncio, exportar Excel, encerrar pelo ícone perto do relógio e reinstalar preservando os dados. O executável não possui assinatura digital do desenvolvedor.

## Publicação e atualização

Siga [o procedimento de publicação](ATUALIZACOES.md) para que o programa reconheça a nova versão. O pacote inclui RadarUpdate.exe, auxiliar que aguarda o fechamento do Radar e instala a versão verificada.
