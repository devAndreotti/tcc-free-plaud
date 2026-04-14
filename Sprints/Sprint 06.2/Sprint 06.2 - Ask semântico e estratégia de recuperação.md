# Sprint 06.2 - Ask semântico e estratégia de recuperação

**Autor:** Codex  
**Data:** 2026-04-13

## Resumo

Esta sprint pega o `ask` estruturado criado antes e o tira do baseline puramente lexical.

Depois da Sprint 06.1, o sistema já deve ter embeddings e vector store reais. O foco agora é ligar essa recuperação semântica ao fluxo de resposta, mantendo citação obrigatória, `no_answer` e contratos estáveis para o frontend.

## Objetivo

Sair de:

`ask -> lexical search -> resposta`

para:

`ask -> semantic search (ou strategy configurável) -> contexto -> resposta com citação`

com capacidade de evoluir depois para busca híbrida e reranking.

## Por que esta sprint existe

O `ask` atual já é útil como baseline:

- resposta estruturada
- claims
- citações
- `no_answer`

Mas ele ainda está apoiado em recuperação lexical simples. O ganho principal agora não é “escrever uma resposta mais bonita”, e sim usar retrieval melhor.

## Escopo desta sprint

### Entram nesta sprint

- integração do `ask` com busca semântica
- estratégia configurável de retrieval
- deduplicação básica de hits
- montagem de contexto mais consistente
- `no_answer` usando sinais do retrieval real
- testes automatizados

### Não entram nesta sprint

- reranker
- calibragem pesada por dataset
- benchmark final
- UI real
- multimodalidade

## Entregáveis

### 1. Estratégia de retrieval configurável

O `ask` deve aceitar ao menos uma estratégia explícita, por exemplo:

- `lexical`
- `vector`

Idealmente preparando terreno para:

- `hybrid`

mesmo que ainda não seja implementada agora.

### 2. Busca semântica integrada ao `ask`

O fluxo de resposta deve usar hits semânticos reais, não apenas substring/token matching.

### 3. Montagem de contexto melhorada

Mesmo sem reranker, a sprint deve:

- reduzir duplicação de chunks muito parecidos
- limitar ruído no contexto
- manter diversidade mínima de evidência quando possível

### 4. Política de `no_answer` mais coerente

O `no_answer` deve usar sinais mínimos como:

- ausência de hits
- score muito baixo
- baixa cobertura
- claims sem citação válida

### 5. CLI mínima para validar o `ask`

Expandir o comando atual para suportar estratégia:

```powershell
uv run free-plaud retrieval ask "C:\caminho\arquivo.md" --question "..." --strategy vector
```

## Critérios de aceite

- o `ask` consegue usar retrieval semântico
- a resposta continua trazendo citação obrigatória
- o contrato de `AskResponse` permanece estável
- `no_answer` continua funcionando
- os testes cobrem retrieval real e abstention mínima

## Backlog em ordem Akita

### Etapa 1 - Escrever testes antes do código

Cobrir:

- `ask` com strategy `vector`
- `ask` com strategy `lexical`
- `no_answer` com score insuficiente
- integridade das citações
- estabilidade do payload

### Etapa 2 - Integrar retrieval real ao `ask`

Trabalhar em:

- `pipeline/src/free_plaud/retrieval/rag.py`
- `pipeline/src/free_plaud/retrieval/search.py`

### Etapa 3 - Expor estratégia no CLI

Trabalhar em:

- `pipeline/src/free_plaud/retrieval/cli.py`

### Etapa 4 - Refinar montagem de contexto

Sem implementar reranker ainda, mas reduzindo:

- redundância
- claims fracas
- repetição desnecessária

### Etapa 5 - Validar em arquivos reais

Rodar o `ask` em arquivos das pastas `samples`.

## Arquivos que provavelmente entrarão

- `pipeline/src/free_plaud/retrieval/rag.py`
- `pipeline/src/free_plaud/retrieval/search.py`
- `pipeline/src/free_plaud/retrieval/cli.py`
- `pipeline/tests/test_rag.py`

## Limites para não colidir com a Sprint 07

### Relação com a Sprint 07

Esta sprint entrega um `ask` melhor, mas não deve:

- virar benchmark completo
- introduzir runner experimental pesado
- calibrar métrica por dataset ainda

## Definition of Done

Esta sprint estará pronta quando:

- o `ask` usar retrieval semântico real
- o contrato continuar estável
- a resposta permanecer auditável por chunk
- a camada ficar pronta para benchmark comparativo

## Nome recomendado para o commit principal

```text
feat(rag): integrate semantic retrieval into ask flow
```
