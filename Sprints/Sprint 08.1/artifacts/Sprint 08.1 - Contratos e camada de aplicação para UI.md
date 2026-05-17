# Sprint 08.1 - Contratos e camada de aplicação para UI

**Autor:** Codex  
**Data:** 2026-04-13

## Resumo

Esta sprint prepara o backend para ser consumido pela interface sem vazar detalhes internos.

O foco não é construir a UI em si, e sim estabilizar a camada de aplicação e os contratos de entrada e saída que o frontend vai consumir.

## Objetivo

Criar uma camada de aplicação limpa entre o domínio do backend e a futura integração com frontend.

## Escopo desta sprint

### Entram nesta sprint

- contratos estáveis para `ask`
- contratos resumidos para notas, fila e benchmark
- camada de serviço/aplicação
- serialização consistente para consumo externo

### Não entram nesta sprint

- PyWebView
- bridge real específica
- Tauri
- polimento visual

## Entregáveis

- camada de serviços para uso pela UI
- contratos estáveis documentados
- payloads coerentes com backend real
- testes de serialização e uso

## Critérios de aceite

- a UI não precisa conhecer módulos internos do backend
- o backend não expõe detalhes de SQLite, ChromaDB ou provider diretamente
- os payloads ficam estáveis o suficiente para mock e integração

## Backlog em ordem Akita

### Etapa 1 - Escrever testes antes do código

Cobrir:

- serialização de `AskResponse`
- serialização de `NoteSummary`
- serialização de `ExperimentRunSummary`

### Etapa 2 - Criar camada de aplicação

Separar casos de uso como:

- `ask`
- `list_notes`
- `list_experiments`

### Etapa 3 - Alinhar contratos com o frontend

Atualizar docs e garantir que o payload real corresponda ao que a UI vai consumir.

## Definition of Done

Esta sprint estará pronta quando:

- o backend estiver pronto para ser ligado à UI sem expor a bagunça interna
- os contratos estiverem estáveis e testados

## Nome recomendado para o commit principal

```text
feat(app): add application layer for ui integration
```
