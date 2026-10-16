# Validação da primeira versão web

Data: 16/10/2026. Dados de teste separados da instalação e dos arquivos pessoais do Radar Windows.

## Verificado localmente

- 26 testes web automatizados: contas vazias e independentes; filtros; favoritos com IDs iguais em contas distintas; tentativa de acessar outra conta; downloads de Excel e CSV; login; convite de uso único/expirado; cookie seguro; origem/Host; CSRF; limite de tentativas; senha/sessão/logout; conta desativada; limite de corpo; URLs não permitidas; agenda sem navegador e após reinício; bloqueio de segunda instância; comparação sem pressupostos da planilha pessoal.
- Proteção de rede testada com destinos privados, resposta DNS mista e conexão ao IP validado preservando a verificação TLS do domínio.
- 151 testes existentes do Windows executados: 150 aprovados e um ignorado por não receber instalador de teste. O teste opcional do instalador já havia sido executado na validação 0.8.4; não foi criado novo instalador Windows para esta entrega.
- Formatação em reais e autocomplete de localidades: testes JavaScript aprovados. Sintaxe dos scripts verificada.
- Teste visual pelo navegador local: entrada com conta fictícia, carregamento dos anúncios, inclusão em favoritos e salvamento de filtro de preço.

## Consulta real pelo novo servidor

Em uma conta de validação, a API autenticada iniciou uma busca real usando o cliente HTTPS restrito da web. Para reduzir consultas, somente a Mega foi ativada, com uma página de catálogo e um novo anúncio.

- Fonte: Mega Leilões.
- Anúncio: [Apartamento de 76 m², Centro, Santa Maria/RS](https://www.megaleiloes.com.br/imoveis/apartamentos/rs/santa-maria/apartamento-76-m2-01-vaga-centro-santa-maria-rs-x129893).
- Horário: 16/10/2026, 20:32, Brasília.
- Resultado: anúncio interpretado, duas etapas identificadas, Excel gerado com sucesso, nenhum erro de leitura nessa amostra.
- A situação global da fonte permaneceu parcial, corretamente, porque o limite configurado interrompeu a expansão do catálogo após a amostra. Isso não significa cobertura completa ou confirmação da disponibilidade do imóvel.

Saraiva, Zuk, Top, Krobel e Superbid mantêm os leitores/limitações anteriores; não houve nova validação de anúncios reais dessas fontes na versão web.

## Hospedagem e limites da verificação

A configuração de produção inclui Docker, volume persistente, servidor Waitress e proxy Caddy. O computador desta validação não tem Docker disponível. O fluxo de integração do repositório inclui testes web no Linux, verificação do Compose, build da imagem e teste HTTP do contêiner.

Não houve publicação em um domínio real, emissão de certificado real, ensaio de restauração Docker, teste de carga ou auditoria externa. O usuário solicitou preparar a versão e as instruções, pois ainda não possui hospedagem. A entrega não equivale a uma garantia de segurança ou capacidade em produção.

Não foram copiados dados da instalação do Windows. O pacote distribuível exclui usuários, bancos, senhas, convites, relatórios de teste e pastas de trabalho.
