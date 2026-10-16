# Atualizações pelo Radar

A partir da versão 0.8, o programa verifica versões estáveis no repositório oficial `pedrocendon/radar-de-leiloes`. Não exige conta do GitHub.

## Para quem usa

1. Se você tem a versão 0.7 ou anterior, instale a versão 0.8 uma única vez. Encerre o Radar pelo ícone perto do relógio antes de abrir esse instalador. Seus dados são mantidos.
2. Nas próximas versões, o Radar mostrará um aviso. Abra **Atualizações** e clique em **Atualizar e reiniciar**.
3. Confirme e aguarde. O programa baixa o arquivo, confere sua integridade, faz uma cópia de segurança, instala e abre novamente.

A verificação automática vem ativada. Acontece ao abrir, após cerca de 20 segundos, e a cada 24 horas enquanto o Radar permanece aberto. Verificações repetidas em menos de um minuto são evitadas. Você pode desativar os avisos automáticos e usar **Verificar agora**. A instalação sempre depende do clique do usuário; uma busca em andamento precisa terminar antes.

O computador precisa estar ligado e conectado à internet. Fechar a janela mantém o Radar ativo perto do relógio. Encerrar o programa ou suspender o computador interrompe a verificação. A partir da versão 0.8.1, a seção Configurações permite ativar a inicialização com o Windows em segundo plano. A opção vem desativada até o usuário escolher ativá-la.

## Dados e recuperação

Os dados permanecem em `%LOCALAPPDATA%\RadarLeiloes`, separados da instalação. Antes de instalar, o programa guarda uma cópia do banco SQLite, favoritos e configurações em `updates\<identificador>\dados-antes-da-atualizacao.zip`. Cada tentativa tem uma pasta própria. Sessões de acesso não entram nessa cópia. Planilhas podem ser geradas novamente a partir do banco.

Se o download falhar, o Radar continua aberto e informa que a atualização não foi concluída. Se o instalador falhar, o auxiliar mostra o erro e tenta reabrir o programa disponível. Não há reversão automática dos arquivos instalados. Em caso de falha parcial, execute o instalador oficial para reparar a instalação. O registro fica em `updates\<identificador>\instalacao.log`. O resultado mais recente aparece na seção Atualizações.

As cópias de segurança ficam no computador, contêm seus dados e não são enviadas ao GitHub. Elas são mantidas para recuperação e podem ocupar espaço. Para restaurar com ajuda do suporte, encerre o Radar, preserve uma cópia dos dados atuais e restaure o conteúdo do ZIP na pasta de dados. Restaurar uma cópia antiga substitui alterações posteriores.

## Segurança e limites

- A consulta usa a API pública do GitHub; o programa não envia anúncios, favoritos ou preferências.
- Só aceita versões estáveis com número `MAJOR.MINOR.PATCH`, superiores à instalada, e o instalador Windows de nome esperado no repositório fixo.
- Exige tamanho e SHA-256 publicados pelo GitHub. Confere ambos antes de executar. HTTPS é obrigatório; redirecionamentos são limitados aos domínios de distribuição do GitHub.
- O auxiliar confere novamente o SHA-256 e a versão do executável, mantém o arquivo bloqueado contra alteração durante sua execução e aguarda o Radar encerrar.
- A atualização usa o mesmo identificador e a mesma pasta da instalação existente, sem elevação administrativa. Não força o encerramento de outros aplicativos nem reinicia o Windows automaticamente.
- O instalador ainda não tem assinatura digital do desenvolvedor. A integridade depende do GitHub e da segurança da conta que publica as versões; SHA-256 não substitui uma assinatura independente.
- Falhas de rede, limites da API e publicações incompletas são mostrados como falha de verificação, sem afirmar que a versão está atualizada.
- A execução diretamente pelo código não instala atualizações automaticamente; esse recurso pertence à versão Windows instalada.

## Publicar uma versão compatível

1. Atualize `version.py`, a versão do Launcher e as versões em `distribution/radar.iss`. Os testes conferem a consistência.
2. Execute os testes e gere o instalador conforme `BUILD.md`. Valide a reinstalação em uma instalação isolada.
3. Crie uma release estável com tag `vMAJOR.MINOR.PATCH`. Envie o arquivo `Instalar-Radar-de-Leiloes-MAJOR.MINOR.PATCH-Windows.exe` (ou `MAJOR.MINOR` quando PATCH for zero) enquanto a release ainda for rascunho.
4. Confirme que o GitHub informa `digest: sha256:...`, o tamanho correto e o estado `uploaded`. Publique e marque como latest apenas após validar os arquivos. Não substitua o instalador de uma versão já publicada: publique um número novo.
5. Consulte a API sem autenticação e teste o download com `updater.release_candidate` e `updater.download`.

Referências: [API de releases do GitHub](https://docs.github.com/en/rest/releases/releases#get-the-latest-release) e [parâmetros do instalador Inno Setup](https://jrsoftware.org/ishelp/topic_setupcmdline.htm).
