---
tags:
- tcc
- arquitetura
- backend
- scaffold
---

# Scaffold inicial do backend Python

Este documento registra a forma escolhida para materializar a primeira base do backend experimental em Python.

A decisão adotada foi manter o backend dentro de `pipeline/`, usando **layout em `src/`**, package principal `free_plaud` e **CLI por subcomandos** com `Typer`. Essa escolha preserva o caráter de monólito modular recomendado pela arquitetura e evita acoplamento prematuro com interface ou shell desktop.

## Estrutura principal

```text
pipeline/
├── pyproject.toml
├── .python-version
├── src/free_plaud/
│   ├── app/
│   ├── ingest/
│   ├── notes/
│   ├── retrieval/
│   ├── benchmark/
│   ├── storage/
│   ├── providers/
│   └── cli.py
└── tests/
```

## Justificativa

| Decisão | Justificativa |
|---|---|
| `pipeline/` como projeto Python isolado | Permite avançar no core experimental antes de UI e desktop |
| `src/free_plaud/` | Melhora ergonomia de testes e packaging |
| `Typer` com subcomandos | Organiza capacidades por domínio e facilita crescimento incremental |
| `providers/` como fronteira própria | Preserva a estratégia BYOK e troca futura de provedores |
| `benchmark/` desacoplado | Reforça o princípio benchmark-first do TCC |

## Responsabilidades dos módulos

| Módulo | Responsabilidade |
|---|---|
| `app` | configuração, caminhos e logging |
| `ingest` | entrada, leitura e validação |
| `notes` | schema e Markdown estruturado |
| `retrieval` | chunking, indexação e busca |
| `benchmark` | datasets, métricas e runners |
| `storage` | persistência local |
| `providers` | contratos de integração externa |

## Estado da implementação inicial

O scaffold atual entrega uma base executável com comandos de inspeção, estruturação de notas, chunking, benchmark demonstrativo e inicialização de persistência local. Ainda não há integração real com SQLite transacional, ChromaDB, parsing completo de PDF ou provedores externos, pois esses pontos pertencem às próximas sprints do backend.
