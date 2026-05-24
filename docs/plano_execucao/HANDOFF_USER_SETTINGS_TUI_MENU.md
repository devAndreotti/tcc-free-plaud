# Handoff - User settings no TUI e menu terminal

Criado em 2026-05-24.

Objetivo: permitir que o usuario altere configuracoes operacionais do app sem editar `.env`.

## Decisao

- `data/results/user_settings.json` guarda preferencias do app.
- `.env` e variaveis de ambiente continuam sendo override tecnico.
- TUI e menu terminal escrevem somente `user_settings.json`.
- Ao mudar `embedding_model` ou `embedding_device`, o runtime limpa cache de embedder/vector store.

## Settings V1

- `embedding_device`: `auto`, `cpu`, `cuda`
- `embedding_model`: `chroma-default` ou `sentence-transformer:<modelo>`
- `retrieval_top_k`
- `default_ask_strategy`: `lexical`, `vector`, `hybrid`
- `default_chunk_size`
- `default_chunk_overlap`
- `corpus_commit_mode`: `auto`, `atomic`, `microbatch`
- `default_corpus_path`
- `corpus_recursive_default`
- `corpus_embedding_batch_size`
- `corpus_index_workers`

## Plano de implementacao

1. Adicionar store de settings editaveis em `app/config.py`.
2. Testar precedencia: `.env`/env acima de `user_settings.json`; JSON acima dos defaults.
3. Criar helpers para ler, salvar e resetar preferencias.
4. Adicionar comandos CLI `config show`, `config set` e `config reset`.
5. Adicionar opcao `Configurações` no menu terminal.
6. Adicionar pane `Settings` no TUI com campos V1.
7. Ao salvar no TUI/menu, limpar `CorpusRuntime` e atualizar labels de navegação.
8. Rodar testes focados, suite completa e smoke de CLI/menu.

## Aceite

- Usuario troca CPU/GPU pelo TUI.
- Usuario troca CPU/GPU pelo menu terminal.
- `user_settings.json` e criado com JSON validado.
- `.env`/env ainda vence `user_settings.json`.
- TUI usa default strategy salvo para Ask.
- Notes usa pasta e recursivo salvos como default.
- Runtime nao reutiliza embedder antigo apos mudanca de modelo/device.

## Status de implementacao

- Store JSON, CLI `config`, menu terminal e pane `Settings` implementados.
- `save_user_settings()` grava preferencias no JSON, limpa cache de settings e retorna a configuracao efetiva quando chamado pelo runtime normal.
- TUI atualiza labels de modelo/device/top_k, strategy default do Ask e pasta default do Notes apos salvar.
- Smoke validado com `FREE_PLAUD_RESULTS_DIR` temporario para nao alterar settings reais do projeto.
- Testes finais: `uv run pytest --basetemp .pytest_tmp` com 206 passed.
