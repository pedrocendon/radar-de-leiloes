# Segurança

O Radar é um aplicativo local para Windows. Seu serviço deve continuar acessível somente em `127.0.0.1`; não o exponha à rede ou à internet.

A edição web tem uma entrada separada (`python -m web.server`), autenticação por conta e armazenamento próprio. Use as instruções de [hospedagem e segurança da web](docs/WEB.md). Não publique o servidor desktop `friendly_ui.py`. A revisão antiga abaixo trata do Windows; os novos controles e limites estão em [VALIDACAO-WEB.md](docs/VALIDACAO-WEB.md).

Consulte a [revisão de 16/10/2026](docs/SEGURANCA-2026-10-16.md), com escopo, evidências e limitações da versão 0.7.

## Relatar um problema

Solicite um canal privado ao mantenedor antes de enviar detalhes de uma vulnerabilidade. Não publique tokens, arquivos de sessão, bancos de dados, configurações pessoais ou logs sem revisão. Para relatar defeitos comuns, use uma reprodução com dados fictícios e informe a versão do Radar e do Windows.

## Antes de distribuir uma versão

- Execute os testes funcionais e de segurança.
- Confira os hashes e a origem dos componentes do instalador.
- Examine o executável com um antivírus atualizado e publique seu SHA-256.
- Confira se o pacote começa sem anúncios, favoritos e preferências de usuários.
- Mantenha as dependências atualizadas e registre as limitações conhecidas.

O instalador 0.7 não tem assinatura digital do desenvolvedor. Nenhuma revisão garante ausência de vulnerabilidades.

O instalador público 0.8.4 também permanece sem assinatura. O processo para assinar as próximas versões está preparado e depende da contratação/configuração de um certificado em nome da empresa. [Situação e limites do SmartScreen](docs/ASSINATURA-WINDOWS.md).
