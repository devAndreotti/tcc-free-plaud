# Sprint 08.2 - Integração inicial backend frontend

**Autor:** Codex  
**Data:** 2026-04-13

## Resumo

Esta sprint faz a primeira ligação real entre o backend e o frontend, mas sem transformar a casca desktop no foco do projeto.

O objetivo é permitir que a interface consuma os contratos já estabilizados em 08.1.

## Objetivo

Ligar o backend real ao frontend com o menor acoplamento possível.

## Escopo desta sprint

### Entram nesta sprint

- adapter de integração
- implementação inicial da bridge ou camada local
- troca de mocks por respostas reais em pontos selecionados
- validação ponta a ponta do fluxo `ask`

### Não entram nesta sprint

- foco em Tauri
- shell desktop final
- polimento amplo de UX

## Entregáveis

- backend consumível pelo frontend
- primeira tela usando `AskResponse` real
- erros e estados vazios tratados minimamente

## Critérios de aceite

- a UI consegue chamar o backend real
- o fluxo mínimo de pergunta e resposta funciona ponta a ponta
- a integração não quebra o isolamento do domínio

## Backlog em ordem Akita

### Etapa 1 - Escrever testes mínimos de integração

Cobrir:

- resposta do backend chegando no contrato esperado
- estado de `no_answer`
- exibição de citações

### Etapa 2 - Implementar bridge/adapter

Escolher o mecanismo de integração de menor acoplamento neste estágio.

### Etapa 3 - Conectar o chat ao backend

Trocar o mock pelo backend real no fluxo mínimo.

## Definition of Done

Esta sprint estará pronta quando:

- o frontend conseguir usar o backend de verdade no fluxo principal
- o contrato do `ask` estiver validado na prática

## Nome recomendado para o commit principal

```text
feat(ui): connect frontend to backend ask flow
```
