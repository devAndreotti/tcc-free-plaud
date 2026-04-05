# Handoff Frontend Joao

## Objetivo deste arquivo

Este arquivo traduz o andamento do backend em necessidades praticas para o frontend.

Ele existe para alinhar a interface com o que o backend vai entregar, sem obrigar integracao real imediata.

## Direcao geral

O frontend pode continuar evoluindo agora, mas deve evitar depender:

- de `string` simples como resposta final
- de PyWebView como contrato definitivo
- de detalhes internos do backend

## O que o frontend deve assumir desde ja

### Chat

O chat deve ser preparado para receber:

- resposta textual
- lista de citacoes
- estado de ausencia de base suficiente
- latencia da resposta

### Notes

A area de notas deve considerar que o backend vai expor ao menos:

- identificador da nota
- titulo
- tipo de origem
- caminho de origem
- tags

### Queue

A fila deve considerar estados como:

- `pending`
- `processing`
- `done`
- `error`

### Benchmark

A tela de benchmark deve considerar listas de execucoes com:

- dataset
- embedding
- chunk size
- overlap
- top-k
- latencia
- metricas

## O que o frontend pode fazer antes da integracao real

### Sprint visual util agora

- trocar mocks livres por mocks baseados no contrato documentado
- adaptar o chat para renderizar citacoes
- prever estado `no_answer`
- modelar cards ou tabelas simples para queue, notes e benchmark

### Beneficio

Quando o backend estiver pronto, a troca sera mais de fonte de dados do que de estrutura de tela.

## Dependencias do frontend em relacao ao backend

### Quando backend entregar `AskResponse`

A interface do chat deve:

- mostrar resposta
- mostrar citacoes
- mostrar mensagem apropriada quando `no_answer = true`

### Quando backend entregar `NoteSummary`

A interface de corpus/notas deve:

- listar notas
- exibir metadados principais
- permitir abrir detalhes depois

### Quando backend entregar `QueueItem`

A interface de fila deve:

- mostrar status por item
- mostrar etapa atual quando existir
- mostrar erro quando existir

### Quando backend entregar `ExperimentRunSummary`

A interface de benchmark deve:

- listar execucoes
- mostrar metricas principais
- permitir comparacao visual simples

## Recomendacao tecnica para o Joao

Hoje, o melhor caminho e:

1. manter a interface separada do backend real
2. substituir o contrato atual baseado em `string`
3. usar mocks tipados
4. deixar a ponte real para depois do backend minimo funcional

## Recado curto para alinhamento

Joao, o backend vai priorizar:

1. nota estruturada
2. chunking e indexacao
3. ask com citacao
4. benchmark

Entao o melhor uso do tempo no frontend agora e preparar a interface para consumir objetos estruturados em vez de resposta textual simples.
