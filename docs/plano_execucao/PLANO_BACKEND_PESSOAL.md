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

## Regra de registro experimental

Todo experimento relevante de retrieval, benchmark ou comparacao de estrategia deve ser registrado em:

- `docs/experimentos/`

Padrao:

- um arquivo novo por experimento relevante
- numeracao sequencial `01`, `02`, `03`...
- nome curto e objetivo

Conteudo minimo:

1. objetivo
2. pergunta ou hipotese
3. corpus ou suite usada
4. comando executado
5. configuracao
6. resultados
7. interpretacao
8. proximos passos

Se o experimento gerar numero util para defesa, benchmark ou texto do TCC, ele deve entrar nessa pasta.

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

## Estado real atual do backend

No estado atual do projeto, o backend ja possui:

- ingestao de `.txt`, `.md` e `.pdf`
- nota canonica persistivel
- chunking com offsets e lineage
- persistencia minima em `SQLite`
- `ask` estruturado com citacao obrigatoria
- regra baseline de `no_answer`

O ponto principal que ainda falta para o pipeline textual ficar mais alinhado ao TCC e:

- embeddings reais
- indexacao vetorial local
- retrieval semantico no `ask`
- benchmark reproduzivel

O ponto principal que agora precisa de calibracao experimental e:

- melhorar a qualidade do retrieval vetorial contra a suite real
- comparar `lexical` vs `vector` de forma repetivel
- registrar os resultados em `docs/experimentos/`

## Sprints concluidas ate agora

### Sprint 00

- scaffold
- `uv`
- configuracao
- CLI
- testes iniciais

### Sprint 01

- schemas centrais
- loaders textuais
- Markdown estruturado

### Sprint 02

- ingestao operacional
- validacao
- logs e rastreabilidade minima

### Sprint 03

- nota canonica
- persistencia local
- manifesto minimo

### Sprint 04.1

- chunking com offsets
- lineage `note -> chunk`
- `chunk_id` estavel

### Sprint 04.2

- persistencia baseline em `SQLite`
- notas
- chunks
- logs
- benchmark records basicos

### Sprint 05

- `ask` estruturado
- citacao obrigatoria
- `no_answer`
- baseline lexical funcionando

## Sprint 06.1 - Embeddings e indexacao vetorial

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

### Objetivo

Adicionar retrieval semantico real ao projeto.

### Entregaveis

- adaptador de embeddings
- persistencia vetorial em `ChromaDB`
- indexacao vetorial dos chunks
- busca semantica baseline

### Criterios de aceite

- uma nota indexada pode ser encontrada por consulta semanticamente semelhante
- o `embedding_model` fica registrado
- a indexacao vetorial nao depende da interface

### Dependencias

- Sprint 05

## Sprint 06.2 - Ask semantico e estrategia de recuperacao

### Objetivo

Ligar o retrieval semantico ao `ask`, mantendo citacao obrigatoria e `no_answer`.

### Entregaveis

- estrategia configuravel de retrieval
- `ask` usando busca semantica real
- montagem de contexto melhorada
- citacao obrigatoria sobre retrieval semantico
- `no_answer` com sinais minimos do retrieval real

## Proximo ciclo experimental recomendado

### Objetivo

Usar a suite real de benchmark para calibrar o retrieval vetorial antes de qualquer prioridade de UI.

### Ordem sugerida

1. rodar `benchmark compare` com a suite atual
2. variar `chunk_size`
3. variar `overlap`
4. trocar `embedding_model`
5. comparar `MRR`, `Recall@3`, `Recall@5`, `Recall@10` e latencia
6. registrar cada rodada relevante em `docs/experimentos/`

### Criterio de saida

So vale seguir para refinamentos maiores de produto quando o retrieval vetorial tiver um baseline experimental defendavel contra a suite real do projeto.

### Resultado experimental atual

Ver:

- `docs/experimentos/01_lexical_vs_vector_suite_baseline.md`
- `docs/experimentos/02_calibracao_retrieval_vetorial.md`
- `docs/experimentos/03_embeddings_alternativos_suite_baseline.md`

Leitura atual:

- `chunk_size = 800` e `overlap = 120` seguem como melhor baseline vetorial entre as variacoes testadas
- os embeddings alternativos testados nao superaram `chroma-default` na suite real
- com a evidencia atual, o proximo ganho provavel nao parece vir de um swap simples de embedding

### Proximo passo recomendado

Antes de qualquer prioridade de UI:

1. manter `800/120 + chroma-default` como baseline vetorial atual
2. abrir ciclo experimental para busca hibrida ou reranking
3. comparar esse proximo ciclo contra `lexical` e contra o baseline vetorial atual

### Criterios de aceite

- toda resposta aponta a base utilizada
- quando nao houver base suficiente, o sistema sinaliza isso
- existe teste cobrindo retrieval semantico no `ask`

### Dependencias

- Sprint 06.1

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

- Sprint 06.2

## Sprint 08.1 - Contratos e camada de aplicacao para UI

### Objetivo

Preparar o backend para consumo limpo pela interface, sem vazar detalhes internos.

### Entregaveis

- contratos estaveis para `ask`
- contratos resumidos para notas e benchmark
- camada de aplicacao/servicos

### Criterios de aceite

- a UI nao precisa conhecer a organizacao interna do backend
- os contratos ficam estaveis o suficiente para mock e integracao real

### Dependencias

- Sprint 07

## Sprint 08.2 - Integracao inicial com a UI

### Objetivo

Conectar o backend real ao frontend no fluxo minimo de `ask`.

### Entregaveis

- adapter ou bridge inicial
- troca de mocks por respostas reais no fluxo principal
- validacao ponta a ponta do chat minimo

### Criterios de aceite

- a UI consegue chamar o backend real
- o fluxo `ask` funciona ponta a ponta

### Dependencias

- Sprint 08.1

## Sprint 09 - Extensoes futuras

### Objetivo

Organizar o que e importante, mas nao entra antes do core textual ficar validado.

### Entregaveis

- reranker
- busca hibrida
- calibragem de thresholds
- audio
- imagem
- shell desktop
- refinamentos de UX

### Criterios de aceite

- essas frentes nao podem comprometer benchmark e core textual

### Dependencias

- Sprint 08.2

## Ordem obrigatoria para IA

Se uma IA for usada para implementar ou pesquisar, ela deve seguir esta ordem:

1. scaffold e testes
2. schemas
3. loaders
4. Markdown estruturado
5. chunking
6. storage
7. `ask` baseline com citacao
8. embeddings e vector store
9. `ask` semantico
10. benchmark
11. contratos de aplicacao para UI
12. integracao com UI

## O que a IA nao deve fazer cedo demais

- nao criar shell desktop como foco principal
- nao construir interface antes do backend minimo
- nao embutir chamada de provedor diretamente em toda a base
- nao misturar benchmark com componentes visuais
- nao implementar audio e imagem antes do core textual

## Definicao de sucesso pessoal

Este plano esta bem executado quando eu tiver:

- backend funcional sem depender do frontend
- retrieval semantico real em vez de apenas baseline lexical
- contrato de integracao claro
- benchmark separado da UI
- caminho limpo para o Joao integrar a interface depois
