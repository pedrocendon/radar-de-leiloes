# Radar web — instalação e uso

## O que foi entregue

Versão web inicial para várias pessoas, cada uma com sua conta. Inclui buscas manuais e automáticas, filtros, favoritos, histórico de avisos, Excel e CSV. Pode ser usada pelo navegador de computadores e celulares.

**Ainda não existe um endereço público desta versão.** Para disponibilizá-la na internet, será necessário um servidor, um domínio e a configuração abaixo. Quem usa o site não precisa instalar Python ou o programa Windows.

## Como a pessoa usa o site

1. Recebe um convite do administrador e abre o link em até 24 horas.
2. Informa seu nome e cria uma senha com pelo menos 12 caracteres.
3. Em **Minha busca**, escolhe cidades, estados, tipo, valores e datas. Campos vazios não limitam a busca.
4. Em **Imóveis acompanhados**, clica em **Buscar novidades**. A situação de cada fonte mostra falhas ou dados incompletos.
5. Usa a estrela para salvar anúncios em **Favoritos**. As alterações detectadas aparecem em **Avisos**.
6. Para consultar automaticamente, ativa a repetição em **Minha busca**. O servidor continua trabalhando depois que a pessoa sai da conta.
7. Baixa o Excel ou CSV. O arquivo é gerado após cada busca; **Atualizar planilha** usa os dados já salvos. Cópias já baixadas precisam ser baixadas novamente para refletir mudanças.

**Sair da conta** encerra o acesso nesse navegador e mantém os dados. Para parar as buscas automáticas, desative a repetição. A senha pode ser trocada em **Configurações → Minha conta**; a troca encerra todas as sessões.

Os avisos desta versão ficam dentro do site. Não há envio por e-mail nem push no celular/Windows. A conta web começa vazia e é independente do aplicativo Windows.

## Experimentar no próprio computador

Requisitos: Windows com Python 3.12 ou 3.13 e internet para a instalação inicial.

1. Extraia o ZIP em uma pasta permanente.
2. Abra **INICIAR-WEB.cmd**. Ele cria um ambiente Python separado e instala as dependências.
3. Deixe essa janela aberta e abra **CRIAR-CONVITE-WEB.cmd**. Informe o e-mail da primeira conta.
4. Copie o link exibido para o navegador e crie sua senha.
5. Nos próximos acessos, use `http://127.0.0.1:8080` enquanto a janela do servidor estiver aberta.

Este endereço funciona somente nesse computador. Fechar a janela do servidor interrompe as buscas locais. Os arquivos ficam em `web-data`, separados dos dados do Radar Windows. Não envie essa pasta a terceiros.

Alternativa pelo terminal, na pasta do projeto:

```powershell
py -3 -m venv .venv-web
.venv-web\Scripts\python -m pip --isolated --disable-pip-version-check install --only-binary=:all: --index-url https://pypi.org/simple pip==26.2
.venv-web\Scripts\python -m pip --isolated install --only-binary=:all: --index-url https://pypi.org/simple -r requirements-web.txt
.venv-web\Scripts\python -m web.manage invite pessoa@exemplo.com
.venv-web\Scripts\python -m web.server
```

Se já existia um ambiente `.venv-web`, execute também os dois comandos de instalação acima para atualizar as ferramentas e dependências. O inicializador verifica a versão do pip antes de iniciar. A revisão de 19/10/2026 encontrou avisos no pip 25.0.1 e verificou o pip 26.2; consulte [a revisão de segurança](SEGURANCA-2026-10-19.md).

## Publicar em um servidor — para o administrador

### Requisitos

- Servidor Linux com Docker e Docker Compose, armazenamento persistente e acesso HTTPS aos leiloeiros.
- Domínio ou subdomínio apontado para o servidor. Portas 80 e 443 disponíveis para o Caddy.
- Uma única instância do Radar. Esta primeira versão usa SQLite e uma fila de trabalho no mesmo processo; não é compatível com múltiplos workers ou réplicas.
- Como ponto inicial de teste, reservar 2 GB de memória para o conjunto servidor/proxy. Isso não representa um teste de capacidade; monitore CPU, memória, disco e duração das filas antes de ampliar o uso.

### Instalação

Extraia o pacote ou obtenha o código do repositório. Na raiz do projeto, crie o arquivo `.env`:

```dotenv
RADAR_DOMAIN=radar.seudominio.com.br
```

Troque o exemplo pelo domínio real. Não inclua `https://` nesse campo. Depois:

```sh
docker compose -f compose.web.yml up -d --build
docker compose -f compose.web.yml ps
docker compose -f compose.web.yml logs --tail=100 radar
```

O Caddy recebe as conexões públicas e encaminha para o Radar pela rede interna. O servidor do Radar não publica a porta 8080 no host. O HTTPS depende do DNS correto e das portas acessíveis. Não publique o servidor desktop nem desative a verificação dos certificados das fontes.

Crie o primeiro convite:

```sh
docker compose -f compose.web.yml exec radar python -m web.manage invite pessoa@exemplo.com
```

Compartilhe o link exibido somente com essa pessoa. O convite vale por 24 horas, aceita um único cadastro e vincula a conta ao e-mail informado pelo administrador. O e-mail não é verificado por mensagem automática; confirme o destinatário antes de entregar o convite. Um novo convite para o mesmo e-mail invalida o anterior.

### Administração das contas

```sh
docker compose -f compose.web.yml exec radar python -m web.manage list
docker compose -f compose.web.yml exec radar python -m web.manage disable pessoa@exemplo.com
docker compose -f compose.web.yml exec radar python -m web.manage enable pessoa@exemplo.com
docker compose -f compose.web.yml exec radar python -m web.manage password pessoa@exemplo.com
```

A redefinição pede a senha sem exibi-la. Use um canal privado para entregar uma senha temporária; a pessoa deve trocá-la ao entrar. Desativar a conta encerra sessões e impede novas buscas; uma coleta que já começou pode terminar. Não existe painel administrativo público nesta versão.

### Dados e backups

O volume Docker `radar_data` contém `/data/accounts.sqlite` e `/data/users/<id>/`. Cada usuário tem seu banco de anúncios, configuração e relatórios. Convites e sessões são guardados como hashes; senhas usam scrypt com salt. O administrador do servidor consegue acessar os dados dos usuários e deve restringir o acesso ao volume e aos backups.

Para uma cópia consistente, aguarde as buscas terminarem, pare o serviço e copie o diretório inteiro. Exemplo, na pasta do projeto, com destino novo:

```sh
docker compose -f compose.web.yml stop radar
docker compose -f compose.web.yml cp radar:/data ./backup-radar-2026-10-16
docker compose -f compose.web.yml start radar
```

Escolha um nome novo a cada backup. Guarde as cópias fora do servidor, com acesso restrito. Para restaurar: pare o serviço, preserve o volume atual como recuperação e copie o conteúdo do backup para `/data`, mantendo o dono UID 10001. Reinicie e confira contas, favoritos e agenda. A restauração não foi ensaiada em Docker neste computador.

### Atualizar o servidor

Faça backup, aguarde as tarefas terminarem, substitua o código pelo novo pacote e execute novamente `docker compose -f compose.web.yml up -d --build`. O volume mantém os dados. Não use `down -v`, pois esse comando apaga os volumes. Os usuários recebem a nova interface ao recarregar a página; não há instalador web para cada usuário.

### Configuração sem Docker

Instale `requirements-web.txt` em um ambiente Python. Configure `RADAR_WEB_DATA` com um diretório persistente e `RADAR_WEB_ORIGIN` com a URL HTTPS completa. Execute `python -m web.server` atrás de um proxy HTTPS. `RADAR_WEB_BIND` é `127.0.0.1` por padrão e `PORT` é `8080`. O servidor recusa HTTP público. A porta interna deve ficar inacessível pela internet. Não use `flask run`, modo debug, múltiplos processos ou armazenamento temporário de hospedagem.

## Segurança e limites da primeira versão

- Autenticação obrigatória, cookies HttpOnly/SameSite e Secure em HTTPS, token contra requisições indevidas, validação de origem/Host e política de segurança do navegador.
- As APIs usam exclusivamente a conta da sessão. Não aceitam caminhos de pastas nem identificadores de outra conta para selecionar dados.
- Downloads autenticados, sem acesso a configurações, bancos, logs ou comandos do Windows.
- Consultas limitadas aos domínios cadastrados, por HTTPS/443. Endereços de rede privada são bloqueados; a conexão fixa o IP validado e verifica o certificado do domínio. Não segue redirecionamentos nem usa proxy informado pelo usuário.
- Até 50 contas; uma tarefa por conta na fila e uma coleta/exportação por vez no servidor. Intervalo mínimo de cinco minutos entre buscas manuais. A partir de 1.000 anúncios salvos, novas consultas são pausadas para revisão pelo administrador; a última busca pode ultrapassar ligeiramente esse limiar. Até 100 links acompanhados por conta.
- Até 10 tentativas de login por e-mail em 15 minutos e 60 tentativas por endereço de conexão. Atrás do proxy, o segundo limite é compartilhado entre visitantes; cabeçalhos de IP enviados pelo cliente não são aceitos como identidade confiável.
- Sessões duram 12 horas. Sair, trocar senha e desativar a conta invalidam sessões no servidor. Até dez sessões por conta.
- Os agendamentos e a próxima execução persistem no disco; após reinício, uma busca vencida volta à fila. Tarefas manuais interrompidas precisam ser solicitadas novamente.
- Não há autenticação em dois fatores, recuperação automática por e-mail, cobrança, cadastro público, exclusão de conta pela interface, migração do Windows ou sincronização com ele. Pedidos de acesso, recuperação e remoção devem ser tratados pelo administrador.
- Os históricos crescem com as consultas. Monitore disco, preserve backups e defina uma política de retenção antes de uso prolongado. A fila simples é adequada à validação inicial; não houve teste de carga para 50 usuários simultâneos.
- A disponibilidade depende da hospedagem. Hospedagens que suspendem processos quando ninguém acessa interrompem o agendamento.

Fontes mantidas: Mega, Saraiva e Zuk com as limitações dos leitores existentes; Top/Krobel com conferência manual; Superbid sem coleta automática. Os catálogos configurados são amostras e não garantem cobertura de todas as cidades ou tipos. O catálogo inicial da Zuk é regional. Nenhum bloqueio de acesso é contornado. [Evidências dos testes](VALIDACAO-WEB.md).

Referências para hospedagem: [Flask com Waitress](https://flask.palletsprojects.com/en/stable/deploying/waitress/), [segurança do Flask](https://flask.palletsprojects.com/en/stable/web-security/) e [proxy do Caddy](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy).
