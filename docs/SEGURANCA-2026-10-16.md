# Revisão de segurança — 16/10/2026

## Resultado

Não foram identificados segredos publicados, dados pessoais do usuário ou falhas críticas nas verificações descritas abaixo. O instalador 0.7 foi examinado pelo Microsoft Defender, que informou não ter encontrado ameaças. Isso é uma revisão delimitada, não uma certificação de ausência de vulnerabilidades.

## Escopo e evidências

- Código remoto até o commit `2fa32c3b9788026fe272855bd8e5241c24eae41e`: 35 arquivos e os sete commits existentes foram conferidos. Busca por chaves privadas, tokens conhecidos, credenciais literais e caminhos pessoais, acompanhada de revisão manual dos componentes de execução.
- Todos os 35 arquivos remotos correspondiam à cópia local revisada, normalizando apenas finais de linha. Os seis módulos Python do pacote de instalação e seu ponto de entrada desktop correspondiam ao código revisado.
- O pacote de compilação não continha bancos SQLite, planilhas, CSV ou logs de usuário. A configuração inicial e a lista de anúncios de referência estavam vazias de preferências pessoais.
- Instalador examinado: `Instalar-Radar-de-Leiloes-0.7-Windows.exe`, 13.474.346 bytes, versão 0.7.0.0. SHA-256: `7ebc4a5c311bc1df77f8889c2dfcbedadce0e7bccfd3302bb900df99ed44f012`. O hash publicado pelo GitHub corresponde ao arquivo local. O Defender fez uma varredura específica desse arquivo, sem remover arquivos.
- 48 testes Python aprovados, incluindo oito verificações de segurança. Os testes JavaScript de valores em reais e localidades também passaram. As verificações usam arquivos temporários e servidores locais, sem atacar sites de leilão.

## Proteções verificadas

- O serviço escuta somente em `127.0.0.1`. As rotas de dados e alterações exigem uma chave aleatória por sessão. Host e origem externos são rejeitados.
- A chave chega à interface pelo fragmento da URL, é removida da barra de endereço e não acompanha os links para leiloeiros. Os dados locais não são enviados ao GitHub pelo programa.
- A interface escapa textos inseridos em HTML e limita links a HTTP/HTTPS. A política de conteúdo bloqueia scripts externos e incorporação em outras páginas. Não há compartilhamento de dados da API por CORS.
- Os arquivos servidos pelo programa ficam em uma lista explícita. Tentativas de ler configurações, sessão e caminhos fora dessa lista falharam. Requisições acima de 1 MB foram rejeitadas.
- As consultas SQL usam parâmetros. CSV neutraliza textos que podem virar fórmulas; o gerador Excel portátil desativa conversão automática de textos em fórmulas.
- O WebView2 não expõe objetos nativos nem mensagens para o JavaScript. Permissões de câmera, microfone e semelhantes são negadas. Sites externos abrem no navegador, fora da janela local.
- O coletor não segue redirecionamentos automaticamente, limita respostas a 6 MB e interrompe consultas diante de desafios ou restrições reconhecidas.

## Dependências e melhoria aplicada

A consulta ao [PyPI para XlsxWriter 3.2.9](https://pypi.org/pypi/XlsxWriter/3.2.9/json) não retornou vulnerabilidades registradas. O arquivo da biblioteca corresponde ao SHA-256 publicado pelo PyPI. Isso não garante ausência de falhas ainda desconhecidas ou não registradas. A [página oficial do Python 3.13.16](https://www.python.org/downloads/release/python-31316/) documenta as correções incluídas nessa versão.

O script de compilação agora também exige o hash correto de XlsxWriter. A validação dos quatro arquivos de entrada usa exceções explícitas, continuando ativa mesmo com Python executado no modo de otimização. Essa mudança protege futuras compilações; não altera o executável 0.7 já distribuído. Os oito testes de segurança foram incluídos na rotina do GitHub Actions.

## Limites e cuidados restantes

- O instalador ainda não possui assinatura digital do desenvolvedor. A assinatura de commits do GitHub não é uma assinatura do executável. O Windows pode avisar que o editor é desconhecido.
- Não foi realizada auditoria completa do Python, .NET, Microsoft WebView2 ou bibliotecas de terceiros. Mantenha Windows e WebView2 atualizados.
- Um programa malicioso executado na mesma conta do Windows pode ler os arquivos locais, inclusive a chave temporária. O Radar não oferece criptografia do banco nem isolamento contra outros processos dessa conta.
- A configuração avançada de fontes é confiada ao usuário local. Não importe configurações de terceiros sem revisão. O coletor não foi projetado como serviço público ou proxy para URLs arbitrárias.
- Os anúncios e editais continuam sendo conteúdo de terceiros. Abrir um link não confirma a legitimidade de um leilão.
- A varredura não substitui análise contínua, revisão de mudanças e atualização das dependências. Dados gerados após a instalação devem continuar fora do repositório.
