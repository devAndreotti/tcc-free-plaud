# Ata - incidente de pagamentos de 09/09/2025

**Data da reunião:** 10/09/2025
**Facilitador:** Paulo Henrique
**Participantes:** Ana Lima Furtado, Bruno Tavares e Larissa Quintela

## Resumo

Na terça-feira, 09/09/2025, entre 14h12 e 14h59, as cobranças por cartão ficaram travadas. Foram 47 minutos com taxa de erro acima de 30%. Os pedidos não se perderam, mas ficaram em status pendente e precisaram de reprocessamento manual.

## Linha do tempo

- 14h12: alerta de latência no gateway de cartão disparou.
- 14h20: plantão abriu o incidente e chamou o SRE.
- 14h41: o Bruno identificou que o timeout do gateway estava em 3 segundos, sem nenhum retry.
- 14h59: o serviço normalizou depois do rollback da mudança feita no dia 08/09.

## Causa raiz

A mudança de 08/09 reduziu o timeout de 10 para 3 segundos por engano, numa alteração que era só de limpeza de configuração. Como não existe retry com jitter, quando o gateway ficou lento, todas as requisições falharam de uma vez e nenhuma tentou de novo.

A Larissa lembrou que a revisão de configuração não pegou a mudança porque o arquivo de timeout não estava no checklist do pull request.

## Ações

1. Restaurar o timeout do gateway para 8 segundos. Responsável: Paulo Henrique, com prazo até 15/09/2025.
2. Adicionar retry com backoff exponencial e jitter, com no máximo 2 tentativas.
3. Criar alerta de p99 acima de 2 segundos no painel de pagamentos.
4. Atualizar o runbook PAY-RB-07 com o passo de rollback que funcionou no incidente.
5. Incluir o arquivo de timeout no checklist de revisão de pull request.

## Observações

O Bruno pediu que a gente não trate o incidente como culpa de uma pessoa. O erro foi do processo, que deixou uma mudança de configuração passar sem revisão específica. A Ana concordou e disse que a discussão de responsabilidade individual não entra na ata.

Ficou combinado que a próxima simulação de falha de gateway vai ser feita em homologação antes do fim do mês.
