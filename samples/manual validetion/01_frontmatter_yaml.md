---
title: Introdução ao Versionamento Semântico em Projetos Python
tags: [python, versionamento, semver, packaging, boas-praticas]
created_at: 2025-02-11T14:32:00-03:00
author: Letícia Drummond
status: rascunho
reviewed: false
---

# Versionamento Semântico: Como Aplicar em Projetos Python do Zero

Manter a compatibilidade entre versões de um pacote Python é uma das decisões técnicas que mais impacta equipes que dependem de bibliotecas internas. Sem uma política clara de versionamento, qualquer atualização pode quebrar silenciosamente pipelines de CI, scripts de automação ou serviços que consomem o pacote.

Este documento descreve como adotar o Versionamento Semântico (SemVer) em projetos Python, cobrindo desde a estrutura do número de versão até a automação com ferramentas como `bump2version` e `commitizen`.

---

## 1. O que é SemVer

O Versionamento Semântico define que um número de versão deve seguir o formato `MAJOR.MINOR.PATCH`, onde:

- **MAJOR** é incrementado quando há mudanças incompatíveis com versões anteriores (breaking changes).
- **MINOR** é incrementado quando novas funcionalidades são adicionadas de forma retrocompatível.
- **PATCH** é incrementado quando correções de bugs retrocompatíveis são feitas.

Além desses três componentes, o SemVer permite sufixos para pré-lançamentos (`1.0.0-alpha.1`) e metadados de build (`1.0.0+build.42`), embora estes últimos sejam ignorados na comparação de versões.

### 1.1 Exemplos Práticos

Considere uma biblioteca de integração com uma API de pagamento:

- Versão `1.3.2 → 1.3.3`: correção de bug no cálculo de juros compostos — PATCH.
- Versão `1.3.3 → 1.4.0`: adição do método `gerar_boleto_parcelado()` sem remover nenhum método existente — MINOR.
- Versão `1.4.0 → 2.0.0`: o método `autenticar()` passou a exigir um argumento obrigatório `client_id` que antes era opcional — MAJOR.

---

## 2. Configurando SemVer em um Projeto Python

### 2.1 Onde armazenar a versão

Existem três abordagens principais para armazenar a versão em um projeto Python:

**Opção A — Variável em `__init__.py`:**
```python
# meu_pacote/__init__.py
__version__ = "1.4.0"
```

**Opção B — Campo em `pyproject.toml`:**
```toml
[project]
name = "meu-pacote"
version = "1.4.0"
```

**Opção C — Versão dinâmica via `importlib.metadata`:**
```python
from importlib.metadata import version
__version__ = version("meu-pacote")
```

A Opção C é a recomendada para projetos que usam `pyproject.toml` como fonte única de verdade, pois evita duplicação.

### 2.2 Automatizando bumps com bump2version

O `bump2version` permite incrementar automaticamente a versão em todos os lugares do projeto onde ela aparece:

```bash
pip install bump2version
bump2version patch   # 1.4.0 → 1.4.1
bump2version minor   # 1.4.1 → 1.5.0
bump2version major   # 1.5.0 → 2.0.0
```

---

## 3. Integração com Git e Changelog

### 3.1 Tags no Git

Cada versão deve corresponder a uma tag no repositório Git:

```bash
git tag -a v1.4.0 -m "Release 1.4.0: adiciona suporte a boleto parcelado"
git push origin v1.4.0
```

### 3.2 Conventional Commits e CHANGELOG automático

Adotar a convenção de commits (`feat:`, `fix:`, `chore:`, `BREAKING CHANGE:`) permite gerar changelogs automáticos com ferramentas como `commitizen` ou `git-cliff`. Isso torna a decisão de qual componente incrementar mais objetiva.

---

## 4. Erros Comuns e Como Evitá-los

- **Incrementar MINOR para um breaking change** é o erro mais prejudicial — quebra contratos implícitos com consumidores do pacote.
- **Não versionar pacotes internos** cria a ilusão de que atualizações são seguras quando não são.
- **Usar versões do tipo `1.0.0-FINAL`** ou `1.0.0-estável` não segue SemVer e dificulta comparações automatizadas.

---

## Referências

- Preston-Werner, T. *Semantic Versioning 2.0.0*. https://semver.org
- Documentação oficial do `bump2version`: https://github.com/c4urself/bump2version
- PEP 440 — Version Identification and Dependency Specification: https://peps.python.org/pep-0440/
