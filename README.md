# Radar de Leilões

Programa para Windows que reúne anúncios de imóveis em leilão, acompanha alterações e organiza favoritos. Versão atual: **0.7**.

## Baixar e instalar no Windows

**[Baixar instalador do Radar 0.7 (.exe)](https://github.com/pedrocendon/radar-de-leiloes/releases/download/v0.7.0/Instalar-Radar-de-Leiloes-0.7-Windows.exe)**

Compatível com **Windows 10 e 11 de 64 bits**. Abra o arquivo baixado, siga o assistente e mantenha marcada a opção de criar o ícone na área de trabalho. Não é necessário instalar Python, Node.js ou Codex.

Se já usa o Radar, encerre-o pelo ícone perto do relógio antes de atualizar. Os dados locais são mantidos. Internet é necessária para as consultas e para instalar o Microsoft WebView2 quando ele ainda não estiver disponível.

[Ver a versão e o guia de instalação](https://github.com/pedrocendon/radar-de-leiloes/releases/tag/v0.7.0). O download é público. Os arquivos “Source code” são destinados ao desenvolvimento; para instalar, escolha o arquivo **.exe**.

## Para quem usa o programa

O instalador abre o Radar em uma janela própria, cria o atalho na área de trabalho e mantém um ícone perto do relógio. A seção **Minha busca** configura os filtros; **Favoritos** reúne os anúncios selecionados. A planilha Excel é atualizada ao concluir uma busca.

Consulte o [guia de uso](docs/COMO-USAR.txt). Ao atualizar, encerre o Radar antes de executar o novo instalador. A instalação mantém os dados locais.

## Recursos

- Busca manual e repetição a cada 1, 6, 12 ou 24 horas enquanto o programa estiver aberto.
- Filtros de cidade, UF, tipo, preço, desconto e data; valores em reais e sugestões de cidades e estados.
- Favoritos persistentes, com pesquisa própria e acesso aos detalhes.
- Histórico de alterações de preço, datas e situação, com preservação dos dados após falhas de consulta.
- Separação entre imóveis, anúncios, leilões e suas etapas; possíveis duplicidades são sinalizadas.
- Excel, CSV e JSON; valores calculados são diferenciados das informações da fonte.

## Fontes e limites

| Fonte | Implementação atual |
| --- | --- |
| Mega Leilões | Consulta de páginas públicas |
| Saraiva Leilões | Páginas e dados públicos incorporados ao HTML |
| Zuk | Consulta parcial de campos reconhecidos |
| Top / Pizzolatti e Krobel | Importação assistida de texto copiado do site |
| Superbid | Consulta automática indisponível |

As consultas respeitam as restrições implementadas para cada fonte. Não há contorno de CAPTCHA, login ou bloqueios. Uma consulta que falha não significa ausência de imóveis. Os catálogos iniciais e os limites de paginação cobrem uma amostra, não todos os imóveis do país. Filtrar uma cidade não amplia o catálogo da fonte.

Os conectores podem precisar de atualização quando os sites mudarem. Confira disponibilidade, datas e edital no site do leiloeiro. O computador precisa estar ligado, sem suspensão e com internet para consultar os sites. Após reiniciar o Windows, abra o Radar novamente.

## Executar a partir do código

Requisitos: Python 3.11 ou superior. Para desenvolvimento:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe run.py
```

Esse comando abre a interface no navegador local. A **janela própria do Windows** é incluída na versão compilada, conforme [instruções de compilação](docs/BUILD.md). A exportação padrão deste comando usa XlsxWriter e não exige Codex ou Node.js.

Outros comandos:

```powershell
python run.py --prepare
python run.py --once
python run.py --export
```

`--prepare` cria `config.json` e `references.json` vazios de preferências pessoais, sem substituir arquivos existentes. Edite `config.json` para configurar fontes adicionais compatíveis ou implemente um novo leitor em `collectors.py`.

## Testes

```powershell
python run.py --prepare
python -m unittest test_monitor test_interface test_portable_excel test_security -v
node test_price.cjs
node test_locations.cjs
```

Node.js 18 ou superior é necessário somente para os testes JavaScript. O módulo `test_xlsx.py` também contém testes do gerador legado baseado em `@oai/artifact-tool`, que requer seu ambiente específico; `test_portable_excel.py` verifica o gerador distribuído com o programa. Os testes comuns utilizam anúncios fictícios e não consultam sites reais.

## Organização

| Arquivo ou pasta | Responsabilidade |
| --- | --- |
| `collectors.py` | Consulta e interpretação de fontes |
| `engine.py` | SQLite, filtros, favoritos, histórico e consolidação |
| `friendly_ui.py` e `ui/` | Serviço local e interface |
| `portable_excel.py` | Planilha distribuída com o programa |
| `distribution/` | Janela Windows, ícone e instalador |
| `config.example.json` | Configuração inicial sem preferências pessoais |

## Dados locais

Este repositório contém o código, os testes e as configurações de exemplo. Planilhas pessoais, bancos de dados, favoritos, relatórios de análise, configurações em uso e sessões de acesso ficam fora do Git.

Na instalação Windows, os dados ficam em `%LOCALAPPDATA%\RadarLeiloes`. No desenvolvimento, ficam nas pastas `data/` e `exports/`, ignoradas pelo Git. Faça backup da pasta de dados com o programa encerrado. Antes de compartilhar logs, retire links privados e informações pessoais.

## Segurança

Consulte a [revisão de segurança](docs/SEGURANCA-2026-10-16.md) e as [orientações de segurança](SECURITY.md). O instalador 0.7 foi examinado pelo Microsoft Defender sem ameaças detectadas. Ele ainda não possui assinatura digital do desenvolvedor. A revisão tem escopo limitado e não garante ausência de vulnerabilidades.

## Dependências e licenciamento

Python, XlsxWriter, Microsoft WebView2, Pillow e Inno Setup mantêm seus próprios termos. As licenças dos componentes distribuídos acompanham o instalador. As sugestões de municípios usam dados públicos do IBGE. Consulte [componentes](docs/COMPONENTES.md).

Uma licença de código aberto para este projeto ainda não foi definida pelo proprietário.
