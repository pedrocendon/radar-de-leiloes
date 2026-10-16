# Assinatura do Radar e aviso do SmartScreen

## Situação em 16/10/2026

O instalador 0.8.4 publicado no GitHub está **sem assinatura Authenticode** (`NotSigned`). O aviso enviado pelo usuário identifica o editor como desconhecido. Não foram encontrados certificados de Code Signing com chave privada nos repositórios pessoais do usuário ou da máquina usados para esta verificação.

O usuário informou que ainda precisa contratar o certificado e escolheu identificar o editor por uma **empresa (CNPJ)**. Não foi contratada assinatura, cobrado valor, instalado certificado ou alterada proteção do Windows. O instalador público 0.8.4 continua igual; ainda não existe uma versão assinada.

## O que contratar

Para identificar a empresa no instalador, procure **OV Code Signing para Windows/Authenticode**, com validação da organização e chave protegida por token/HSM ou serviço de assinatura compatível com SignTool. Não é certificado TLS de site nem e-CNPJ para documentos fiscais.

Uma opção para cotação é [SSL.com OV Code Signing](https://www.ssl.com/products/software-integrity/code-signing/ov/). O serviço [eSigner](https://www.ssl.com/products/software-integrity/signing-service/) oferece assinatura em nuvem com adaptador CKA para SignTool. A integração preparada usa o certificado no repositório do Windows, inclusive quando o fornecedor disponibiliza a chave por token ou adaptador. Serviços que oferecem apenas API própria precisam de integração específica.

Antes de pagar, confirme com a certificadora:

- Emissão para a empresa brasileira e quais documentos serão exigidos.
- Razão social exata que aparecerá como editor no Windows.
- Preço total do certificado e da assinatura, incluindo token, entrega, assinatura em nuvem e limites por operação.
- Compatibilidade com `signtool.exe`, SHA-256 e carimbo de tempo RFC 3161.

Não foi confirmada uma proposta comercial nem a elegibilidade de um CNPJ específico. A documentação atual do Azure Artifact Signing limita a validação pública a uma lista de países que **não inclui o Brasil**, embora exista uma região de infraestrutura Brazil South. A localização do servidor não equivale à elegibilidade da empresa: [requisitos oficiais](https://learn.microsoft.com/en-us/azure/artifact-signing/quickstart).

## O que a assinatura resolve

Identifica o editor e permite verificar se o executável mudou depois de assinado. O SmartScreen também considera a reputação do arquivo e do editor: **a assinatura, inclusive EV, não garante o desaparecimento imediato do aviso**. Não há prazo ou quantidade de downloads garantidos. Não recomende pagar mais por EV apenas para tentar eliminar esse alerta.

Para evitar o aviso de download pelo fluxo da loja, a alternativa é distribuir um pacote MSIX certificado pela Microsoft Store. Isso envolve outro empacotamento e processo de publicação; a entrega atual continua sendo um instalador EXE pelo GitHub. [Orientação da Microsoft sobre reputação](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/smartscreen-reputation), [opções de assinatura e distribuição](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/code-signing-options).

## Preparação técnica implementada

`distribution/Build-SignedInstaller.ps1`:

1. Confere a presença do certificado indicado, chave privada acessível, finalidade Code Signing, validade e cadeia de confiança/revogação do Windows.
2. Prepara o pacote existente e assina Radar.exe, RadarTray.exe e RadarUpdate.exe.
3. Verifica cada assinatura, o certificado esperado e o carimbo de tempo; qualquer falha interrompe o processo.
4. Recalcula os hashes do pacote após assinar.
5. Usa a integração do Inno Setup para assinar o instalador e o desinstalador, preenchendo o editor a partir do certificado.
6. Verifica o instalador final e grava SHA-256 e relatório de assinatura em uma pasta nova dentro de `dist/signed/`.

O modo `-CheckOnly` confere os pré-requisitos sem compilar ou assinar. O processo não publica automaticamente no GitHub, exporta chaves ou recebe senha em argumento. Não instale certificados raiz artificiais nos computadores dos usuários para simular confiança.

### Executar depois de contratar e configurar o certificado

Instale o SDK oficial do Windows (SignTool) e o software oficial do fornecedor do certificado. O certificado precisa estar em `Cert:\CurrentUser\My` ou `Cert:\LocalMachine\My`, com sua chave disponível ao provedor. Use o endereço de carimbo de tempo indicado pela certificadora. Não envie chave privada, PIN ou senha pelo chat ou pelo GitHub.

Exemplo de parâmetros, que precisam ser preenchidos com os valores reais:

```powershell
$assinatura = @{
    CertificateThumbprint = 'SUBSTITUA_PELO_THUMBPRINT_DE_40_CARACTERES'
    SignToolPath = 'C:\caminho-do-sdk\signtool.exe'
    InnoSetupPath = 'C:\Program Files (x86)\Inno Setup 6\ISCC.exe'
    PythonPath = 'C:\caminho-do-python\python.exe'
    TimestampServer = 'https://SERVIDOR-DE-TEMPO-DA-CERTIFICADORA'
}
.\distribution\Build-SignedInstaller.ps1 @assinatura -CheckOnly
.\distribution\Build-SignedInstaller.ps1 @assinatura
```

Siga também os pré-requisitos de [BUILD.md](BUILD.md). O script requer PowerShell no Windows e não altera a política de execução. Certificados instalados em LocalMachine exigem o parâmetro `-CertificateStore LocalMachine` e permissões adequadas para usar a chave.

### Antes de publicar a primeira versão assinada

- Incremente a versão conforme [ATUALIZACOES.md](ATUALIZACOES.md); não substitua o EXE da release 0.8.4.
- Revise a razão social exibida e valide a assinatura em outro Windows com a cadeia pública normal de certificados.
- Teste instalar/reinstalar, abrir a janela, usar a bandeja, atualizar e desinstalar em ambiente isolado; confira também a assinatura do desinstalador instalado.
- Examine o arquivo final com o antivírus e verifique seu download e hash depois da publicação.
- Registre separadamente a validade da assinatura e a ocorrência do SmartScreen. Uma assinatura válida não é um teste da reputação do SmartScreen.

## Validação desta preparação

A integração foi preparada sem certificado contratado. É possível verificar a sintaxe e a recusa de compilação sem identidade de assinatura. **A assinatura real, o carimbo de tempo, a integração com token/nuvem e a ausência do aviso ainda não foram testados**, pois dependem do certificado e do serviço escolhidos.

Verificações realizadas: análise sintática do PowerShell sem erros; tentativa com certificado ausente recusada antes de compilar ou assinar; compilador Inno recusou `SignedBuild` sem `PublisherName`. O SignTool não foi encontrado no SDK local durante a preparação. Nenhum executável foi alterado ou publicado nesta etapa.

Referências técnicas: [SignTool](https://learn.microsoft.com/en-us/windows/win32/seccrypto/signtool), [assinatura no Inno Setup](https://jrsoftware.org/ishelp/topic_setup_signtool.htm) e [desinstalador assinado](https://jrsoftware.org/ishelp/topic_setup_signeduninstaller.htm).
