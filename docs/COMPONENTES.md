# Componentes e fontes

O código do Radar ainda não possui uma licença de código aberto escolhida pelo proprietário. As licenças dos componentes abaixo continuam aplicáveis.

| Componente | Uso | Referência |
| --- | --- | --- |
| Python 3.13.16 | Execução do programa instalado | https://www.python.org/downloads/ |
| SQLite 3.54.1 | Banco de dados do instalador 0.8.5; DLL oficial substitui 3.50.4 do Python | https://sqlite.org/download.html |
| XlsxWriter 3.2.9 | Exportação Excel portátil | https://pypi.org/project/XlsxWriter/3.2.9/ |
| Microsoft WebView2 SDK 1.0.4258.31 | Janela Windows | https://www.nuget.org/packages/Microsoft.Web.WebView2/1.0.4258.31 |
| Microsoft WebView2 Runtime | Exibição da interface | https://developer.microsoft.com/microsoft-edge/webview2/ |
| Inno Setup 6 | Criação do instalador | https://jrsoftware.org/isinfo.php |
| Pillow | Geração do ícone durante a compilação | https://pypi.org/project/Pillow/ |
| openpyxl | Validação de arquivos Excel nos testes | https://pypi.org/project/openpyxl/ |
| IBGE | Lista de municípios e estados para autocompletar | https://servicodados.ibge.gov.br/api/v1/localidades/municipios |

A lista de localidades foi incorporada à interface em 02/10/2026. Ela funciona sem consultar a API a cada digitação. O instalador inclui os textos de licença de Python, XlsxWriter e WebView2.

`report_builder.mjs`, `xlsx_export.py` e `test_xlsx.py` mantêm a integração legada com o ambiente de geração de planilhas usado no desenvolvimento. A execução por `run.py`, o instalador e os testes principais usam `portable_excel.py`, sem depender dessa integração.

Os anúncios pertencem às fontes indicadas em `config.example.json`. A disponibilidade dos sites, seus termos de uso e as permissões de coleta devem ser respeitados. Falhas de acesso são registradas como falhas, sem representar ausência de imóveis.
