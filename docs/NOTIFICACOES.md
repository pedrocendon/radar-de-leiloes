# Avisos de novos imóveis

Disponíveis na versão instalada do Radar 0.8.3 para Windows 10 e 11.

## Usar

1. Salve pelo menos um filtro em **Minha busca** e ative a repetição automática.
2. Em **Configurações**, mantenha **Avisar no Windows quando encontrar novos imóveis** marcado. **Testar aviso** envia uma mensagem identificada como teste.
3. Feche a janela pelo X. O ícone perto do relógio mantém o Radar em execução.
4. Clique no aviso para abrir o Radar e consulte **Avisos**. A página mostra as últimos 50 grupos de avisos, motivos e links.

Os avisos vêm ativados. Desmarque a opção para desativar. Ative também **Iniciar o Radar automaticamente com o Windows** se quiser retomar as buscas ao entrar na sua conta. As buscas manuais também podem gerar avisos.

## O que conta como novidade

Um imóvel novo para o Radar, lido em uma fonte habilitada e com dados suficientes para atender aos filtros salvos. Preço, desconto e data precisam combinar na mesma etapa. Etapas com data passada e situações conhecidas de encerramento, cancelamento ou venda são excluídas. Dados incompletos aguardam uma leitura suficiente, mesmo quando a lista principal permite resultados pendentes.

Cada busca agrupa as novidades em um aviso. O histórico é salvo no banco local, juntamente com os filtros usados. Anúncios existentes ao instalar, trocar os filtros ou reativar avisos não são enviados como novidades. Uma mudança de preço em anúncio já avaliado fora dos filtros não é tratada como imóvel novo.

Identificações comprovadas do mesmo imóvel evitam avisos duplicados. Links de várias fontes encontrados juntos são preservados. Endereços parecidos sem identificação segura continuam separados, podendo gerar avisos distintos.

## Limitações

O computador precisa estar ligado, sem suspensão e com internet; o Radar deve permanecer em execução. **Encerrar programa** interrompe os avisos. A cobertura depende dos catálogos e leitores de cada fonte; importações assistidas e falhas de consulta não geram alertas.

O Windows controla a exibição e a duração dos avisos. Confira **Configurações do Windows → Sistema → Notificações**, incluindo **Não incomodar**. O histórico permanece no Radar mesmo quando o Windows oculta um aviso. A confirmação da entrega à interface é gravada antes de solicitar o aviso para evitar repetição; uma interrupção nessa passagem pode impedir o balão, mas não apaga o histórico. Não há garantia de permanência na central de notificações.

O histórico registra o momento da consulta. Confira disponibilidade e edital na fonte. O teste pode ser solicitado uma vez por minuto e não adiciona imóveis fictícios ao histórico.

## Implementação

A fila e as preferências ficam no SQLite do usuário e integram a cópia de segurança das atualizações. O processo da bandeja consulta a fila pela interface local autenticada e usa [NotifyIcon.ShowBalloonTip, da Microsoft](https://learn.microsoft.com/en-us/dotnet/api/system.windows.forms.notifyicon.showballoontip?view=netframework-4.8.1). Não exige contas, senhas ou serviços externos de notificações.

## Favoritos: preço e data

Em **Configurações → Avisos dos favoritos**, ative ou desative cada tipo de aviso. Ambos vêm ativados; a antecedência padrão é 3 dias, com opções de 1 e 7 dias. Esses avisos independem dos filtros e da opção de avisar sobre imóveis novos.

O preço comparado é o lance mínimo da mesma etapa, data e identificação de leilão disponível. A primeira leitura forma uma referência, sem inventar quedas anteriores. Mudanças de data ou de leilão iniciam outra comparação. Não se compara o lance da primeira praça ao da segunda nem a avaliação ao lance. Cada redução detectada pode gerar aviso, inclusive outra redução após uma alta. Valores ausentes ou inválidos preservam a referência anterior. Reativar avisos de preço usa os valores atuais como nova referência.

Os lembretes são verificados a cada minuto com o Radar em execução, sem depender de uma nova busca naquele momento. Exigem leitura bem-sucedida nas últimas 48 horas e fonte habilitada; falhas recentes impedem o uso de dados antigos. Portanto, ative a repetição das buscas. Um favorito adicionado já dentro do prazo também pode gerar lembrete. A etapa e a data são lembradas uma única vez, inclusive entre reinícios e remoção/reinclusão nos favoritos. Alterações da data podem gerar outro lembrete. Quando a fonte informa hora, o horário passado é excluído; sem hora, considera-se o dia inteiro. A antecedência é medida em dias de calendário no horário de Brasília.

Ao remover um favorito, avisos pendentes daquele anúncio não são entregues. Antes da entrega, o Radar revalida a seleção, a situação conhecida e a etapa. O histórico permanece como registro do momento da consulta, mesmo que a informação mude. Favoritos com identidade comprovada e mesma alteração detectada na mesma consulta são agrupados, preservando os links.

São avisos informativos com base na leitura disponível; a fonte pode mudar entre consultas. Confirme o edital. O modo de concentração do Windows pode ocultar o balão. A fila persistente evita repetição após reiniciar, mas não garante exibição pelo sistema.
