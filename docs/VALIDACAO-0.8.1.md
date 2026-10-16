# Validação da versão 0.8.1 — 16/10/2026

- 78 testes Python passaram, incluindo instalação isolada pelo atualizador e 11 testes novos da inicialização com o Windows.
- Testados: ativar/desativar, salvar e consultar a preferência, remoção externa do registro, falhas de permissão, preservação de entradas de outros programas, rejeição de parâmetros inválidos, abertura manual versus segundo plano e retomada de agenda ativada.
- O iniciador C# foi compilado e testado para aceitar somente o argumento de segundo plano, usar Python sem console e preservar caminhos com espaços.
- Uma cópia nativa do pacote foi iniciada em segundo plano com dados isolados. Confirmados: servidor disponível, leitura real da configuração do Windows, segunda tentativa de abertura sem criar outra sessão e encerramento completo pela interface local.
- A nova página foi conferida visualmente. A ativação e a desativação foram exercitadas com um registro simulado, sem alterar a inicialização real do computador do usuário.
- Testes JavaScript de moeda e localidades passaram.
- Instalador de produção compilado, inclusive a remoção da entrada de inicialização durante a desinstalação. O teste de instalação usa um identificador isolado e não modifica a instalação normal.
- Microsoft Defender: nenhuma ameaça detectada no instalador.

Não foi reiniciado o Windows do usuário para validar um login real. O mecanismo usado é a chave Run documentada pela Microsoft. Políticas do computador e desativação pelo Windows podem impedir a inicialização; a interface explica como conferir isso.

Arquivo: `Instalar-Radar-de-Leiloes-0.8.1-Windows.exe`

SHA-256: `de754f7050513119fff9d96f0008ee755e412844734b56eccdf2943cc751eb9b`

O instalador continua sem assinatura digital do desenvolvedor. As verificações não garantem ausência de vulnerabilidades.

Para repetir os testes, execute `python -m unittest test_monitor test_interface test_portable_excel test_security test_updater test_native_updater test_startup -v`, `node test_price.cjs` e `node test_locations.cjs`. O teste opcional de instalação usa `RADAR_TEST_INSTALLER` com uma compilação feita com `/DValidationBuild`, conforme o procedimento descrito na validação da versão 0.8.
