# Ata da reunião de migração de filas para o Kafka

**Data:** 12/03/2025
**Participantes:** Ana Lima Furtado (tech lead), Bruno Tavares (SRE), Carla Mendes (produto), Diego Sampaio (backend)

## Contexto

A gente vem discutindo há umas três semanas se continua com o RabbitMQ na fila de eventos de pedidos ou se migra pro Kafka. O problema principal hoje é que o consumer de faturamento perde mensagem quando o broker reinicia, e o time passa um tempão reprocessando na mão. A Ana lembrou que o volume já passou de 4 mil pedidos por minuto nas sextas à noite, então o problema não é mais teórico.

Bruno comentou que o RabbitMQ aguenta bem o volume atual, mas que o retry de mensagem morta é um script de 300 linhas que ninguém quer mexer. Diego concordou e disse que o wrapper do producer em Python precisa ser reescrito de qualquer jeito.

## Decisões

- Vamos migrar o fluxo de eventos de pedidos para o Kafka. O RabbitMQ continua só para os e-mails transacionais, que não entram nessa rodada.
- O tópico principal se chama pedidos-v2 e vai ter 12 partições, com replication factor 3. O Bruno achou 12 um bom número porque deixa folga pra crescer sem precisar re-particionar logo.
- Retenção de 7 dias. A Carla queria 30, mas o custo de disco no staging ficou alto e a gente cortou pra 7 por enquanto. Isso volta pra discussão no fim do trimestre.
- O producer vai usar acks=all com idempotência ligada. O Diego vai expor só o wrapper, e ninguém deve chamar o client cru direto no código de negócio.

## Discussão sobre ordem

Ordem só é garantida dentro da partição, então a chave de partição vai ser o pedido_id. Se alguém precisar de ordem global por cliente, aí é outra conversa, porque hoje o cliente_id concentra muito tráfego e ia dar desequilíbrio entre as partições.

Ana perguntou se a gente precisava de exactly-once de ponta a ponta. A resposta foi não, por enquanto. O consumer de faturamento vai ser idempotente pelo número do pedido, e isso resolve o caso que dói hoje.

## Pendências

- Definir o runbook de reprocessamento de offset. Responsável: Bruno, com revisão da Ana.
- Medir a latência p99 no ambiente de homologação antes da próxima revisão.
- A Carla leva a discussão de retenção para o comitê de custos.
- Diego vai montar um consumer de exemplo para o time de faturamento testar.

## Próximos passos

O cutover ficou marcado para o dia 22/03/2025, das 23h às 2h da manhã. O rollback é simples: reativar o consumer antigo pela feature flag ORDERS_LEGACY_CONSUMER, sem precisar de deploy. A Ana avisa o atendimento no dia 20, e o Bruno deixa um canal aberto no Slack durante a janela.
