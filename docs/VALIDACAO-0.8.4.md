# Validação do Radar 0.8.4

Data: 16/10/2026. Escopo: mudanças de data/horário, suspensão e cancelamento de leilões dos favoritos.

## Resultados

- 151 testes Python aprovados, incluindo 25 novos casos de alterações, migração das preferências 0.8.3, integração com a coleta e atualização com instalador real em destino isolado.
- Testes JavaScript de valores em reais e sugestões de localidades aprovados; sintaxe da interface verificada.
- Interface conferida com favorito explicitamente fictício: data anterior/nova, situação publicada, histórico, opções independentes e persistência após recarregar.
- Processo nativo em segundo plano: novas preferências aceitas, aviso identificado como teste solicitado e fila consumida, abertura duplicada evitada e encerramento limpo.
- Microsoft Defender examinou o instalador final sem detectar ameaças.

## Casos cobertos

Datas válidas, horário alterado, equivalência de fusos, ganho de precisão sem mudança confirmada, etapas ausentes/duplicadas, novo leilão, perda de identidade conhecida, suspensão e cancelamento explícitos, situação desconhecida, retomada seguida de nova suspensão, falhas de rede/bloqueio/404, importação assistida, fontes desativadas, retirada dos favoritos, migração sem avisos retroativos, reinício, disputa de entrega, avisos substituídos por informação posterior e agrupamento entre fontes comprovadas.

O leitor Mega foi exercitado com HTML controlado contendo situação no painel, sem confundir uma menção condicional de cancelamento no texto. O fluxo de coleta foi testado com mudança confirmada para cancelado, inclusive preservação do aviso quando a exportação Excel falha.

## Limitações

Não foram provocadas alterações em anúncios reais. Os testes usam dados controlados e não certificam a disponibilidade atual dos sites. A suspensão/cancelamento depende do campo de situação extraído: Mega dispõe dessa leitura; códigos desconhecidos de Saraiva e leitores sem situação, como Zuk/genérico, não permitem confirmar esses eventos. A ausência de aviso não confirma que o leilão continua ativo.

A solicitação ao processo nativo foi confirmada, mas não a exibição visual do balão pelo Windows. Não incomodar e políticas do sistema podem ocultá-lo. Não houve reinício completo do Windows nesta validação. A instalação e os dados pessoais em uso não foram alterados.

## Instalador

- Arquivo: `Instalar-Radar-de-Leiloes-0.8.4-Windows.exe`
- Tamanho: 13492774 bytes
- SHA-256: `28f1d8f861c3c8e173430072ced2049676f6f271c1df086b30e1f9fa9db0c3cc`
- Sem assinatura digital do desenvolvedor.
