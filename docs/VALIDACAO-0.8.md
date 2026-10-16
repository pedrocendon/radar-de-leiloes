# Validação da versão 0.8 — 16/10/2026

## Resultado

- 62 testes Python de coleta, filtros, favoritos, interface, segurança, exportação e atualização passaram.
- 5 testes do auxiliar Windows passaram: espera pelo encerramento do processo, pedido de reabertura, bloqueio de arquivo alterado, bloqueio de versão divergente, tratamento de erro do instalador e instalação real isolada (alguns casos verificam mais de um comportamento).
- Os testes JavaScript de valores monetários e sugestões de cidades/estados passaram.
- Na instalação real isolada, o auxiliar executou uma compilação Inno com identificador exclusivo de teste. A versão instalada abriu seu servidor no autoteste e gerou a planilha Excel. A reabertura foi capturada pelo teste; a interface real de produção do usuário não foi encerrada nem alterada.
- A cópia de segurança foi restaurada em um banco temporário e os dados foram conferidos. O arquivo de sessão com credencial local ficou fora do ZIP.
- O novo código consultou a API pública do GitHub e baixou o instalador publicado da versão 0.7, conferindo os 13.474.346 bytes e o SHA-256 esperado. Nenhum downgrade foi instalado.
- A nova tela foi conferida no navegador local, incluindo navegação e o botão Verificar agora com consulta real ao GitHub.
- O instalador 0.8 foi examinado pelo Microsoft Defender: nenhuma ameaça detectada.

## Arquivo distribuído

`Instalar-Radar-de-Leiloes-0.8-Windows.exe`

SHA-256: `b8f5671883c27bc7a0dc0f9eb7104b77aa94b71b266cdfdd12b46db390f231ea`

O executável não tem assinatura digital do desenvolvedor. As verificações realizadas não garantem ausência de vulnerabilidades. Consulte [o funcionamento, a recuperação e os limites de segurança](ATUALIZACOES.md).

## Repetir a validação

Execute na raiz do repositório, em Windows:

```powershell
python run.py --prepare
python -m unittest test_monitor test_interface test_portable_excel test_security test_updater test_native_updater -v
node test_price.cjs
node test_locations.cjs
```

O teste de instalação Inno é opcional e fica desativado na integração contínua. Para executá-lo, compile **somente** uma variante com `/DValidationBuild` e configure `RADAR_TEST_INSTALLER` com o caminho desse arquivo. Execute `python -m unittest test_native_updater -v`. O teste utiliza uma pasta temporária e remove sua própria instalação ao terminar. Nunca forneça o instalador de produção nesse teste: ele compartilha o identificador da instalação normal do usuário.
