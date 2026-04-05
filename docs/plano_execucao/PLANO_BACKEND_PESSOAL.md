# Plano de Execucao Backend Pessoal

## Objetivo deste arquivo

Este arquivo existe para servir como guia operacional do backend.

Ele deve ser usado por:

- mim, como roteiro de execucao
- IA, como instrucao de ordem, foco e criterio de pronto

Este plano segue a arquitetura atual do projeto:

- backend e benchmark antes da interface rica
- foco inicial em texto e PDF
- UI so entra de verdade depois do primeiro fluxo completo com citacao

## Contexto atual do projeto

O projeto `tcc-free-plaud` e um TCC sobre pipeline local-first de captura multimodal, estruturacao em Markdown e recuperacao semantica com citacao obrigatoria em portugues brasileiro.

O foco cientifico principal nao e a casca desktop.
O foco principal e provar experimentalmente:

1. ingestao
2. estruturacao
3. indexacao
4. RAG com citacao
5. benchmark

## Regra de execucao

Executar nesta ordem.
Nao pular para UI real antes do backend minimo funcional.
Nao acoplar o backend ao PyWebView ou a qualquer shell desktop.
Nao espalhar logica de benchmark pelo frontend.
Nao acoplar o sistema a um unico provedor desde o inicio.

## Ambiente oficial

- Python `3.12.x`
- `uv`
- `Typer`
- `Pydantic`
- `SQLite`
- `ChromaDB`
- `Pytest`

## Definicao de pronto global

O backend saiu da fase conceitual quando conseguir:

1. receber um `.pdf`
2. extrair texto
3. gerar uma nota Markdown estruturada
4. indexar em banco vetorial local
5. responder uma pergunta com citacao
6. ter testes cobrindo esse fluxo minimo

## Estrutura-alvo do backend

```text
pipeline/
├── app/
├── ingest/
├── providers/
├── notes/
├── retrieval/
├── benchmark/
├── storage/
└── cli.py
```

## Sprint 00 - Ambiente e esqueleto

### Objetivo

Criar a base minima do backend sem implementar regra de negocio pesada.

### Entregaveis

- scaffold Python com `uv`
- estrutura inicial de pastas
- configuracao inicial por `Pydantic`
- entrada CLI com `Typer`
- suite inicial de testes com `Pytest`

### Criterios de aceite

- o projeto instala e roda localmente
- existe comando CLI inicial
- existe pasta de testes funcionando
- o backend ainda nao depende da UI

### Nao fazer ainda

- nada de PyWebView
- nada de Tauri
- nada de audio e imagem

## Sprint 01 - Schemas e Markdown

### Objetivo

Definir as estruturas centrais do dominio.

### Entregaveis

- schema `Note`
- schema `Chunk`
- schema `AskResponse`
- schema `ExperimentRun`
- serializer Markdown com frontmatter

### Criterios de aceite

- os schemas validam dados corretamente
- a nota final separa texto bruto e texto estruturado
- o Markdown gerado e consistente e testado

### Dependencias

- Sprint 00

## Sprint 02 - Ingestao de texto e PDF

### Objetivo

Permitir que o backend receba arquivos reais e extraia conteudo bruto.

### Entregaveis

- loader de `.txt`
- loader de `.md`
- loader de `.pdf`
- validacao de tipo de arquivo
- normalizacao minima do texto extraido

### Criterios de aceite

- arquivos de texto entram no pipeline com rastreabilidade
- PDF gera texto bruto util
- falhas de parsing ficam registradas de forma clara
- testes cobrem casos basicos e um ou dois PDFs reais

### Dependencias

- Sprint 01

## Sprint 03 - Estruturacao da nota

### Objetivo

Transformar o conteudo bruto em nota Markdown consistente.

### Entregaveis

- montagem de `Note` a partir do conteudo extraido
- preenchimento de metadados minimos
- geracao de frontmatter
- persistencia local da nota estruturada em arquivo ou area definida

### Criterios de aceite

- a nota final tem formato previsivel
- origem e metadados ficam rastreaveis
- existe teste do fluxo bruto -> nota

### Dependencias

- Sprint 02

## Sprint 04 - Chunking e persistencia basica

### Objetivo

Preparar a base de recuperacao semantica com rastreabilidade forte.

### Entregaveis

- algoritmo de chunking
- offsets ou referencias de origem por chunk
- persistencia de metadados em `SQLite`
- vinculo `note -> chunk`

### Criterios de aceite

- cada chunk aponta para a nota de origem
- o sistema preserva ordem dos chunks
- o chunking e testado

### Dependencias

- Sprint 03

## Sprint 05 - Embeddings e indexacao

### Objetivo

Indexar o acervo local para busca semantica.

### Entregaveis

- adaptador de embeddings
- persistencia vetorial em `ChromaDB`
- indexacao dos chunks
- busca semantica inicial

### Criterios de aceite

- uma nota indexada pode ser encontrada por consulta semelhante
- o embedding model fica registrado
- a indexacao nao depende da interface

### Dependencias

- Sprint 04

## Sprint 06 - Ask com citacao obrigatoria

### Objetivo

Fechar a primeira fatia forte do TCC.

### Entregaveis

- pipeline de pergunta
- recuperacao `top-k`
- montagem de contexto
- resposta com citacao obrigatoria
- regra de ausencia de base suficiente

### Criterios de aceite

- toda resposta aponta a base utilizada
- quando nao houver base suficiente, o sistema sinaliza isso
- existe teste de citacao obrigatoria

### Dependencias

- Sprint 05

## Sprint 07 - Benchmark

### Objetivo

Transformar o backend em instrumento experimental defensavel.

### Entregaveis

- schema de dataset de benchmark
- runner de experimento
- metricas `MRR`, `Recall@k` e latencia
- exportacao de resultados
- persistencia de execucoes em `SQLite`

### Criterios de aceite

- um conjunto de experimentos pode ser reproduzido
- os resultados podem ser exportados
- configuracoes testadas ficam registradas

### Dependencias

- Sprint 06

## Sprint 08 - Preparacao para integracao com a UI

### Objetivo

Expor o backend de forma limpa para consumo futuro da interface.

### Entregaveis

- contrato estavel de resposta para `ask`
- contrato resumido para fila, notas e benchmark
- camada de adaptacao pronta para ser ligada a bridge, HTTP local ou outro mecanismo

### Criterios de aceite

- a UI consegue se integrar sem precisar conhecer logica interna do backend
- a integracao futura nao exige reescrever o dominio

### Dependencias

- Sprint 07

## Ordem obrigatoria para IA

Se uma IA for usada para implementar ou pesquisar, ela deve seguir esta ordem:

1. scaffold e testes
2. schemas
3. loaders
4. Markdown estruturado
5. chunking
6. storage
7. embeddings
8. ask com citacao
9. benchmark
10. integracao com UI

## O que a IA nao deve fazer cedo demais

- nao criar shell desktop como foco principal
- nao construir interface antes do backend minimo
- nao embutir chamada de provedor diretamente em toda a base
- nao misturar benchmark com componentes visuais
- nao implementar audio e imagem antes do core textual

## Definicao de sucesso pessoal

Este plano esta bem executado quando eu tiver:

- backend funcional sem depender do frontend
- contrato de integracao claro
- benchmark separado da UI
- caminho limpo para o Joao integrar a interface depois
