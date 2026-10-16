# Avisos de novos imóveis

Disponíveis na versão instalada do Radar 0.8.4 para Windows 10 e 11.

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

## Mudança de data, suspensão e cancelamento

Em **Configurações → Avisos dos favoritos**, há duas opções independentes, ativadas por padrão: **Avisar quando a data ou o horário do leilão de um favorito mudar** e **Avisar quando o leilão de um favorito for suspenso ou cancelado**. A atualização preserva as opções anteriores de preço e lembretes.

As mudanças são verificadas depois de cada consulta, incluindo buscas automáticas com a janela fechada. Não dependem dos filtros nem do prazo dos lembretes. A data anterior, a nova data, a situação publicada, os links e a última leitura ficam no histórico de **Avisos**. Suspensões e cancelamentos têm prioridade de entrega sobre os demais avisos dos favoritos.

A comparação de datas exige duas datas válidas para a mesma etapa e anúncio, sem alteração da identificação do leilão. Horários equivalentes em fusos diferentes não geram alerta. Acrescentar ou retirar um horário no mesmo dia também não confirma mudança; horários diferentes geram alerta quando ambos eram informados. Etapas sem número ou duplicadas são ignoradas. Campos ausentes ou inválidos preservam a última referência, sem gerar cancelamento ou mudança. Alterações entre duas datas já passadas não geram aviso.

Um leilão com identificação diferente inicia outra referência. Quando uma identificação conhecida desaparece, o Radar aguarda uma leitura que confirme o evento. Se a fonte nunca informa identificação do leilão, compara-se a mesma etapa do mesmo anúncio; reutilização do anúncio pela fonte pode exigir conferência manual.

Suspensão e cancelamento exigem situação explícita reconhecida no campo do anúncio. Não se interpreta uma menção genérica no texto, uma possibilidade de cancelamento, código numérico desconhecido, inatividade, página removida ou falha de consulta como cancelamento. Mudanças para situação ativa permitem reconhecer uma suspensão posterior como um novo evento.

A primeira leitura forma uma referência. Instalar a atualização, favoritar ou reativar opções não envia ocorrências antigas. Informações incompletas e consultas com erro aguardam confirmação. Retirar o favorito, desativar a fonte ou receber uma atualização que substitui a informação impede a entrega de um aviso pendente obsoleto. O histórico é preservado.

### Cobertura das fontes

O leitor Mega já extrai a situação do painel do anúncio. Saraiva atualmente preserva o código de situação e identifica inatividade; códigos sem correspondência confirmada não são traduzidos para suspensão ou cancelamento. Zuk e o leitor genérico ainda não extraem uma situação específica. A importação assistida não gera estes avisos. Datas podem ser acompanhadas nas fontes em que as etapas são reconhecidas. Portanto, a ausência de aviso não confirma que o leilão continua ativo. Confira o site e o edital.
