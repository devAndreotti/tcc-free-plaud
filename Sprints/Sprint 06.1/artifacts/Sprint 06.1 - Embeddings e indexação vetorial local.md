# Sprint 06.1 - Embeddings e indexação vetorial local

**Autor:** Codex  
**Data:** 2026-04-13

## Resumo

Esta sprint fecha o maior buraco técnico atual do projeto: hoje já existe ingestão, nota canônica, chunking com offsets, persistência em SQLite e um `ask` com citação obrigatória, mas a recuperação ainda é apenas lexical.

O objetivo desta sprint é introduzir o primeiro baseline real de recuperação semântica:

`note -> chunks -> embeddings -> ChromaDB -> semantic search`

Sem essa camada, o sistema até consegue responder perguntas, mas ainda não se comporta como um pipeline RAG experimental completo.

## Objetivo

Sair de um cenário em que o retrieval é apenas:

`query -> lexical search -> chunks`

para um cenário em que exista:

`query -> embedding -> vector search -> hits semânticos`

mantendo a rastreabilidade `note -> chunk -> citation`.

## Por que esta sprint existe

O estado atual do projeto já sustenta:

- ingestão de `.txt`, `.md` e `.pdf`
- nota estruturada persistida localmente
- chunking com offsets reproduzíveis
- persistência mínima em SQLite
- `ask` estruturado com citação obrigatória e `no_answer`

Mas ainda faltam dois elementos centrais do TCC:

- embeddings reais
- indexação vetorial local

Sem isso:

- o RAG continua preso a busca lexical
- o benchmark futuro mede pouco sobre recuperação semântica
- o projeto fica desalinhado com a própria proposta de arquitetura

## Escopo desta sprint

### Entram nesta sprint

- adapter real de embeddings
- implementação real do vector store local
- persistência vetorial dos chunks
- indexação por chunk com metadados
- busca semântica inicial com score
- testes automatizados desse fluxo

### Não entram nesta sprint

- reranker
- busca híbrida completa
- calibragem fina de thresholds
- benchmark completo
- integração com UI
- lógica multimodal

## Estado atual do código

Hoje o código já tem placeholders bons para esta etapa:

- `pipeline/src/free_plaud/providers/embed.py`
- `pipeline/src/free_plaud/storage/vector.py`
- `pipeline/src/free_plaud/retrieval/indexer.py`
- `pipeline/src/free_plaud/retrieval/search.py`

O problema é que essas peças ainda não formam um retrieval semântico de verdade.

## Entregáveis

### 1. Adapter de embeddings

Criar uma implementação concreta por trás do protocolo de `Embedder`.

Requisitos mínimos:

- receber `list[str]`
- devolver `list[list[float]]`
- permitir troca futura de provedor
- registrar o nome do modelo usado

O baseline pode ser local ou remoto, desde que a interface fique limpa e testável.

### 2. Vector store local real

Substituir o placeholder atual de `LocalVectorStore` por uma implementação real baseada em `ChromaDB`.

Essa camada deve:

- criar ou abrir uma coleção local
- indexar embeddings por `chunk_id`
- guardar metadados do chunk
- permitir consulta por embedding de pergunta

### 3. Persistência vetorial por chunk

Cada chunk indexado deve carregar metadados suficientes para suportar retrieval auditável, como:

- `chunk_id`
- `note_id`
- `note_version`
- `chunk_index`
- `char_start`
- `char_end`
- `strategy`
- `pipeline_version`

### 4. Busca semântica inicial

Criar uma função de busca semântica que devolva hits com score.

Formato mínimo esperado:

- `chunk`
- `score`
- `strategy`

Não precisa ainda misturar lexical e vector.

### 5. CLI mínima de indexação e busca

Adicionar ou expandir comandos como:

```powershell
uv run free-plaud retrieval index "C:\caminho\arquivo.md"
uv run free-plaud retrieval semantic-search "C:\caminho\arquivo.md" --query "pergunta"
```

O objetivo é validar o fluxo sem UI.

## Critérios de aceite

- um documento pode ser indexado no vector store local
- uma pergunta semanticamente parecida recupera chunks relevantes
- o modelo de embedding usado fica identificável
- a indexação não depende da interface
- o fluxo tem testes automatizados

## Backlog em ordem Akita

### Etapa 1 - Escrever testes antes do código

Cobrir:

- adapter de embedding
- criação da coleção vetorial
- indexação de chunks com metadados
- busca semântica retornando hits
- persistência local entre execuções

### Etapa 2 - Implementar o adapter de embeddings

Trabalhar em:

- `pipeline/src/free_plaud/providers/embed.py`

ou criar módulos concretos ao redor dele.

### Etapa 3 - Implementar `ChromaDB`

Trabalhar em:

- `pipeline/src/free_plaud/storage/vector.py`

com interface pequena e compatível com evolução futura.

### Etapa 4 - Ligar indexação aos chunks

Expandir:

- `pipeline/src/free_plaud/retrieval/indexer.py`

para permitir:

- chunking
- embedding
- escrita no vector store

### Etapa 5 - Expor busca semântica

Expandir:

- `pipeline/src/free_plaud/retrieval/search.py`

para incluir algo como:

- `semantic_search(...)`

### Etapa 6 - Validar tudo via CLI e suíte completa

Executar:

```powershell
uv run pytest
```

e testar manualmente:

```powershell
uv run free-plaud retrieval index "C:\caminho\arquivo.md"
uv run free-plaud retrieval semantic-search "C:\caminho\arquivo.md" --query "pergunta"
```

## Arquivos que provavelmente entrarão

- `pipeline/src/free_plaud/providers/embed.py`
- `pipeline/src/free_plaud/storage/vector.py`
- `pipeline/src/free_plaud/retrieval/indexer.py`
- `pipeline/src/free_plaud/retrieval/search.py`
- `pipeline/src/free_plaud/retrieval/cli.py`
- `pipeline/tests/test_vector_store.py`
- `pipeline/tests/test_search.py`

## Limites para não colidir com a Sprint 06.2

### Relação com a Sprint 06.2

Esta sprint prepara a recuperação semântica, mas não deve:

- trocar totalmente o `ask`
- introduzir busca híbrida completa
- fazer reranking
- mudar o contrato da UI sem necessidade

## Definition of Done

Esta sprint estará pronta quando:

- existir indexação vetorial local de verdade
- existir busca semântica inicial utilizável
- o projeto deixar de depender exclusivamente de retrieval lexical
- a próxima sprint puder integrar isso ao `ask` com baixo atrito

## Nome recomendado para o commit principal

```text
feat(retrieval): add local vector indexing baseline
```
