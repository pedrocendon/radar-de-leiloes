# Validação do Radar 0.8.2

Data: 16/10/2026. Escopo: avisos de novos imóveis no Windows e histórico local.

## Resultado

- 98 testes Python aprovados, incluindo 20 casos de notificações e o teste opcional de atualização com instalador real em destino isolado.
- Testes JavaScript de valores em reais e sugestões de localidades aprovados.
- Compilação dos executáveis Windows e dos instaladores de validação e distribuição concluída.
- Processo nativo iniciado em segundo plano em pasta de teste: fila de aviso de teste consumida pelo processo da bandeja, sem abrir janela; preferência persistida; abertura duplicada evitada; encerramento limpo.
- Interface conferida: histórico com anúncio explicitamente fictício, motivos, links, ativação/desativação persistente após recarregar e botão de teste.
- Microsoft Defender examinou o instalador abaixo e não detectou ameaças.

## Casos cobertos

Primeira migração sem alertar anúncios antigos; filtros e fontes alterados sem retroagir; avisos desativados e reativados; ausência de filtros; dados pendentes e erros de leitura; preço e data na mesma etapa; datas passadas; situações encerradas; duplicidades comprovadas entre fontes; reinício do programa; disputa entre entregas concorrentes; histórico persistente e preservação do aviso mesmo se a exportação Excel falhar.

## Limites da validação

Os testes usam dados controlados e não certificam a cobertura ou disponibilidade atual dos sites de leilão. A integração nativa confirmou a solicitação ao Windows e o consumo da fila; não houve confirmação visual do balão no desktop nem teste de todas as políticas de notificações do Windows. O modo de concentração e as preferências do sistema podem ocultar avisos. Não foi realizado reinício completo do Windows nesta validação. A instalação e os dados pessoais em uso não foram modificados.

## Instalador

- Arquivo: `Instalar-Radar-de-Leiloes-0.8.2-Windows.exe`
- Tamanho: 13485706 bytes
- SHA-256: `6767c0bcc86f28e63ded954268a97322154e19266d8e02fa8623de349c931bae`
- Sem assinatura digital do desenvolvedor.
