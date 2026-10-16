# Iniciar com o Windows

Disponível a partir da versão 0.8.1 instalada para Windows.

## Ativar ou desativar

Abra **Configurações** e marque **Iniciar o Radar automaticamente com o Windows**. A alteração é salva na hora. Na próxima entrada na sua conta do Windows, o Radar inicia em segundo plano, com o ícone perto do relógio. A janela aparece ao abrir pelo atalho ou dar dois cliques no ícone.

Para desativar, desmarque a opção. Isso impede a próxima inicialização automática e mantém a sessão atual aberta. Use **Encerrar programa** para parar o Radar agora. Encerrar manualmente não desmarca a preferência para o próximo login.

A opção vem desativada até você ativá-la. Ela vale apenas para sua conta do Windows e não exige administrador. Atualizações feitas pelo Radar mantêm a preferência. Desinstalar remove a entrada de inicialização que aponta para essa instalação.

## Buscas automáticas

Ative também **Minha busca → Buscar automaticamente** e salve a repetição. Com essa agenda ativada, iniciar em segundo plano agenda uma consulta após cerca de 30 segundos; depois, o Radar segue o intervalo escolhido. Se a agenda estiver desativada, abrir com o Windows mantém o Radar disponível, sem iniciar buscas nos sites.

O computador precisa estar ligado, sem suspensão e com internet. O Radar usa o mesmo controle de instância da abertura manual, para evitar duas cópias trabalhando simultaneamente.

## Se não iniciar

- Confira se a opção está marcada no Radar.
- Em **Configurações do Windows → Aplicativos → Inicialização**, confira se o Radar está permitido. O Radar não sobrescreve bloqueios definidos pelo Windows ou pelo administrador.
- O Windows pode atrasar a abertura dos aplicativos de inicialização. A execução ocorre ao entrar na conta, não antes do login.
- Caso tenha movido a instalação para outra pasta, abra o Radar dessa pasta e ative novamente a opção.
- A execução diretamente pelo código, no navegador, não oferece essa configuração.

## Implementação

O programa registra somente o valor `RadarLeiloesAutoStart` em `HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run`, na visão de 64 bits. O comando contém o caminho completo do próprio `Radar.exe`, entre aspas, seguido de `--background`. A interface não pode escolher outro executável ou comando. Desativar remove somente esse valor; não altera entradas de outros programas. Abrir o Radar apenas consulta o registro, sem reativar a opção por conta própria.

O iniciador aceita apenas o argumento conhecido e inicia `pythonw.exe` sem console, repassando `--no-browser` à aplicação. O processo de segundo plano não abre a janela. A consulta da configuração é protegida pela mesma interface local autenticada; gravações são recusadas durante uma atualização do programa.

Referência: [documentação Microsoft das chaves Run e RunOnce](https://learn.microsoft.com/en-us/windows/win32/setupapi/run-and-runonce-registry-keys).
