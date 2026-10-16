# Avisos de novos imóveis

Disponíveis na versão instalada do Radar 0.8.2 para Windows 10 e 11.

## Usar

1. Salve pelo menos um filtro em **Minha busca** e ative a repetição automática.
2. Em **Configurações**, mantenha **Avisar no Windows quando encontrar novos imóveis** marcado. **Testar aviso** envia uma mensagem identificada como teste.
3. Feche a janela pelo X. O ícone perto do relógio mantém o Radar em execução.
4. Clique no aviso para abrir o Radar e consulte **Novos imóveis**. A página mostra as últimas 50 buscas com novidades, motivos e links.

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
