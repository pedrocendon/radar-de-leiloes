# Validação do Radar 0.8.3

Data: 16/10/2026. Escopo: avisos de preço e lembretes de leilão dos favoritos.

## Resultados

- 126 testes Python aprovados: incluem 26 testes específicos dos favoritos, preferências pela interface autenticada, agenda de lembretes independente de busca, regressões de avisos de imóveis novos e atualização real com instalador em destino isolado.
- Testes JavaScript de valores em reais e sugestões de cidades/estados aprovados.
- Preferências conferidas na interface: alteração da antecedência, ativação/desativação e persistência após recarregar. Histórico conferido com favoritos explicitamente fictícios, preço anterior/atual, redução, data e última leitura.
- Processo nativo em segundo plano: novas preferências salvas, aviso identificado como teste solicitado e fila consumida, abertura duplicada evitada e encerramento limpo.
- Microsoft Defender não detectou ameaças no instalador final.

## Casos relevantes

Comparação apenas da mesma etapa/data/leilão; novas reduções após aumentos; preço ausente ou inválido; falha e recuperação; dados antigos; datas inválidas, passadas e horários já encerrados; leilão cancelado ou adiado; remoção e reinclusão nos favoritos; reinício; fontes desativadas; filtros de busca independentes; desativação e reativação dos avisos; agrupamento de favoritos comprovadamente iguais; revalidação antes da entrega.

## Limites

Os testes usam dados controlados; não certificam a cobertura atual dos leiloeiros. A solicitação do aviso ao processo nativo foi confirmada, mas não sua exibição visual pelo Windows. Políticas do Windows e Não incomodar podem silenciar notificações. Não foi realizado reinício completo do computador nesta validação. A instalação e os dados pessoais em uso foram preservados.

Lembretes dependem de uma leitura bem-sucedida nas últimas 48 horas. A antecedência usa dias de calendário no horário de Brasília. Uma alteração de data inicia nova comparação de preço. Não se presume continuidade entre leilões distintos.

## Instalador

- Arquivo: `Instalar-Radar-de-Leiloes-0.8.3-Windows.exe`
- Tamanho: 13493443 bytes
- SHA-256: `97c07fdfe296f5f5ffa05941302c044de40f5652844551fcd4f6ca250fdde05f`
- Sem assinatura digital do desenvolvedor.
