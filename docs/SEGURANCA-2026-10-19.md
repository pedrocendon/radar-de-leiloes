# Revisão de segurança — 19/10/2026

## Conclusão

A revisão encontrou pontos que precisavam de correção. O Radar 0.8.5 atualiza o SQLite do instalador, restringe a consulta à sessão local e ativa proteções adicionais do banco de dados. A preparação da edição web também foi corrigida para atualizar o pip antes de instalar dependências.

Os testes descritos abaixo passaram e o Microsoft Defender não encontrou ameaças no novo instalador. **Isso não certifica ausência de vulnerabilidades.** Não foi identificado um caminho de exploração remota das falhas de SQLite pelas rotas examinadas, mas a dependência antiga foi substituída mesmo assim. Recomenda-se atualizar o Radar 0.8.4 e versões anteriores.

## O que foi encontrado e corrigido

| Ponto | Evidência e alcance | Tratamento |
| --- | --- | --- |
| SQLite antigo no Windows | O instalador 0.8.4 incluía SQLite 3.50.4, com FTS5 habilitado e modo defensivo desativado. Os registros CVE-2026-11822 e CVE-2026-11824 abrangem versões anteriores a 3.53.2 e descrevem corrupção de memória sob condições específicas. | O instalador 0.8.5 inclui a DLL oficial SQLite 3.54.1. O build confere o SHA3-256 publicado pelo fornecedor e a versão efetivamente carregada. As conexões do programa, das contas web e dos backups ativam o modo defensivo, desativam confiança no esquema e carregamento de extensões. |
| Redirecionamento na retomada da sessão local | Uma reprodução controlada mostrou que a consulta de inicialização seguia HTTP 302 e encaminhava o cabeçalho do token. Dependia de interferência no serviço/porta local; não foi demonstrado acesso remoto aos dados. | A consulta aceita somente `http://127.0.0.1:porta/`, sem credenciais, caminho extra, fragmento ou consulta. Não usa proxy nem segue redirecionamentos, valida a chave e limita a resposta a 16 KiB. |
| pip antigo no ambiente de preparação web | O ambiente de teste usava pip 25.0.1. A consulta ao PyPI apontou seis CVEs distintos, com condições como instalação de pacotes/índices maliciosos; um deles tem mitigação adicional nas versões recentes do Python. O executável desktop não inclui pip. | Ambiente de teste atualizado para pip 26.2. Inicializador web, Docker, instruções e CI passam a atualizar o pip antes da instalação e usar o índice oficial com pacotes binários. Nova verificação de dependências no CI. |

O Radar usa consultas SQL parametrizadas, não oferece execução de SQL enviado pelo usuário e não importa bancos de terceiros. A análise dessas condições reduz a exposição identificada ao SQLite; não substitui a atualização do componente. As referências oficiais são o [registro CVE-2026-11822](https://www.cve.org/CVERecord?id=CVE-2026-11822), o [registro CVE-2026-11824](https://www.cve.org/CVERecord?id=CVE-2026-11824) e a [avaliação dos mantenedores do SQLite](https://sqlite.org/cves.html).

## Verificações realizadas

### Código, histórico e dados distribuídos

- Base remota revisada: commit `45ab30a76c53ca1064fb699411416a9bd2fd6ed7`, com 84 arquivos. Todos correspondiam à cópia local antes das alterações, normalizando finais de linha.
- Foram pesquisados 17 commits e 176 objetos de conteúdo distintos, aproximadamente 2,67 MB, por padrões de chaves privadas, tokens GitHub, identificadores de acesso AWS, chaves Google, tokens Slack e URLs com credenciais. Nenhuma correspondência nesses padrões. A pesquisa não detecta todo formato possível de segredo.
- O payload anterior tinha 112 arquivos, todos consistentes com seu manifesto. Não havia SQLite, planilhas, CSV, logs, arquivos de chave ou `.env` distribuídos. Referências, links acompanhados e filtros iniciais estavam vazios.
- Os 13 módulos Python do payload foram comparados ao código. As diferenças anteriores em `engine.py` e `portable_excel.py` correspondiam à edição web adicionada depois da versão 0.8.4.
- A compilação 0.8.5 tem 113 arquivos, incluindo a identificação do novo SQLite. A lista de inclusão e os dados iniciais foram conferidos novamente. O `.gitignore` também passa a excluir arquivos de chave `.pfx` e `.p12`.

### Testes de proteção e regressão

- 183 testes Python aprovados na execução final, incluindo instalação de validação isolada pelo auxiliar nativo, preservação de um favorito, geração do Excel e confirmação do SQLite 3.54.1 instalado.
- Os dois conjuntos JavaScript de preços e localidades passaram.
- Testes de acesso sem token, Host/Origin indevidos, arquivos fora da lista permitida, tamanho de requisição e redirecionamentos.
- Testes de isolamento entre contas, favoritos com identificadores iguais, arquivos de outras contas, CSRF, cookies seguros, expiração, logout, revogação de sessões e limitação de tentativas de login.
- Testes de coleta web que bloqueiam destinos privados e DNS misto, validam domínio/porta e conectam ao IP verificado preservando a validação TLS do nome original.
- Testes de atualização que recusam instaladores alterados, versões divergentes, downloads incompletos, origens não permitidas e downgrade; backup preserva os dados e exclui o token temporário.
- Testes de fórmula maliciosa em CSV/Excel e de SQL tratado como dado. Novos testes confirmam que o modo defensivo bloqueia alteração direta do esquema SQLite.

Os testes usaram dados fictícios e diretórios temporários. A instalação de validação tem identificação própria; o Radar instalado do usuário e seus dados não foram substituídos. Tentativas iniciais esbarraram em restrições do ambiente de testes e em biblioteca de validação ausente; a execução final corrigiu essas condições. Não foram feitos testes ofensivos contra os sites de leilões.

### Análise estática e dependências

- Bandit 1.9.4: nenhum alerta alto ou médio na revisão final. Os 16 alertas baixos foram examinados: importação/uso de subprocessos com argumentos separados e caminhos controlados; abertura do Excel gerado; valor sentinela de senha inválida; e duas verificações por `assert` no empacotador de desenvolvimento. Não são 16 vulnerabilidades confirmadas.
- pip-audit 2.10.1: nenhum aviso conhecido para os 13 pacotes do ambiente web/testes após a atualização, incluindo pip 26.2. A resolução dos dois arquivos de requisitos também não retornou avisos para seus 12 pacotes. Resultado limitado às bases consultadas nessa data.
- O índice oficial de vulnerabilidades NuGet não retornou avisos para `Microsoft.Web.WebView2`, SDK usado na versão 1.0.4258.31. Isso não substitui a atualização do WebView2 Runtime instalado no Windows.
- Python incluído: 3.13.16; OpenSSL: 3.5.9. Conferidas as [notas do Python](https://www.python.org/downloads/release/python-31316/) e os [avisos da linha OpenSSL 3.5](https://openssl-library.org/news/vulnerabilities-3.5/index.html). O OpenSSL observado corresponde à versão corrigida dos avisos mais recentes consultados.
- Assinaturas de `python.exe`, da biblioteca WebView2 Core e do instalador auxiliar WebView2 foram reconhecidas como válidas, respectivamente da Python Software Foundation e Microsoft.
- Foram revisados os pontos de execução C#, navegação WebView2, abertura de links, permissões, comandos do instalador e do atualizador. Não há ponte de objetos nativos exposta ao JavaScript da interface.

### Antivírus e integridade

Microsoft Defender 4.18.26090.9: nenhuma ameaça detectada nas varreduras específicas do instalador 0.8.4, do payload anterior e do instalador 0.8.5. As varreduras foram executadas sem remediação automática. A primeira chamada ao executável antigo do Defender falhou; a ferramenta da plataforma atual concluiu as verificações.

| Arquivo | Tamanho | SHA-256 |
| --- | ---: | --- |
| Instalar-Radar-de-Leiloes-0.8.4-Windows.exe | 13.492.774 bytes | `28f1d8f861c3c8e173430072ced2049676f6f271c1df086b30e1f9fa9db0c3cc` |
| Instalar-Radar-de-Leiloes-0.8.5-Windows.exe | 13.903.154 bytes | `811e5631be662c6f762d94a9a2b700ea276579bd3ef2942c8821ab81768d593f` |

O hash do instalador 0.8.4 foi comparado ao informado pela API pública do GitHub. O componente SQLite 3.54.1 veio de `https://sqlite.org/2026/sqlite-dll-win-x64-3540100.zip`; seu SHA3-256 é `c2d09c8babb9399277055c057c97a53f1ffd7c5f11d0c1f2118ffdfa39f2daa4`, conforme a [página oficial de downloads](https://sqlite.org/download.html).

## Limitações e riscos restantes

1. **O instalador 0.8.5 continua sem assinatura Authenticode do Radar.** O certificado empresarial ainda depende de contratação. O aviso de editor desconhecido/SmartScreen pode continuar; não foi desativada nenhuma proteção do Windows.
2. O atualizador depende da integridade do GitHub e da conta publicadora. HTTPS e hash não substituem uma identidade de assinatura independente. Não foram auditadas a autenticação multifator, permissões administrativas ou segurança da conta GitHub.
3. Não houve auditoria completa dos binários de terceiros, fuzzing abrangente, pentest independente ou teste de carga prolongado. Windows, .NET, WebView2 e componentes do servidor precisam de manutenção própria.
4. A edição web ainda não tem implantação pública. O SQLite da hospedagem depende do Python/sistema operacional usado: mantenha-o corrigido e confira sua versão e avisos antes de publicar. As proteções das conexões estão ativas também na web, mas a DLL Windows não atualiza servidores Linux.
5. Os bancos e backups não são criptografados pelo Radar. Um programa executado com acesso aos arquivos da mesma conta pode lê-los ou alterá-los. Não compartilhe a pasta de dados nem importe configurações de origem desconhecida.
6. Na web, a limitação de login por IP vê o endereço do proxy na configuração inicial. Isso evita confiar em cabeçalhos falsificados, mas tentativas abusivas podem limitar temporariamente usuários legítimos. É necessário avaliar proteção de borda e capacidade antes de ampliar a hospedagem.
7. A origem, autenticidade e regularidade dos anúncios/editais não são garantidas pelo programa. A revisão de segurança não valida um leilão.

## Como receber a correção

No Radar 0.8 ou superior, use **Atualizações → Verificar agora → Atualizar e reiniciar**, quando a versão 0.8.5 estiver disponível. Alternativamente, use o instalador 0.8.5 publicado na [página de versões](https://github.com/pedrocendon/radar-de-leiloes/releases/latest). Os testes confirmaram preservação dos dados no processo verificado.

As evidências técnicas desta execução foram guardadas localmente em `work/security-2026-10-19/`: inventário, consultas às bases de vulnerabilidades, resultados dos testes, análise estática, logs de compilação e antivírus. Essa pasta não faz parte da distribuição.
