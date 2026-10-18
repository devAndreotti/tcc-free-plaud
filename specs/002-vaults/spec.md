# Feature Specification: Vaults (corpora independentes)

## Summary
Uma **vault** é um espaço de trabalho com nome, ícone (do conjunto do app) e cor. Cada vault tem
seu próprio banco (SQLite + Chroma), suas pastas de origem, sua Fila, seu grafo, suas notas e
suas conversas. O usuário cria, renomeia, troca e exclui vaults; tudo na interface diz respeito à
vault ativa. Ex.: "Obsidian" (vault pessoal) e "Culinária" (receitas), sem misturar respostas.

## Decisões (confirmadas pelo dono em 2026-10-18)
- **Isolamento físico:** um SQLite + uma coleção Chroma por vault, em `data/vaults/<id>/`.
- **Conversas por vault:** as abas do chat pertencem à vault ativa.
- **Ícone:** um dos ícones do próprio app (`UI/src/components/Icons.tsx`) + uma cor de uma paleta
  fixa. Sem emoji.
- **Grafo lido do corpus:** o grafo mostra as notas indexadas da vault ativa (não mais a varredura
  de uma pasta solta). Clicar numa nota abre ela na tela Notas.

## Modelo
`data/vaults.json` (escrita atômica):
```json
{ "active": "obsidian",
  "vaults": [ { "id": "obsidian", "name": "Obsidian", "icon": "notes", "color": "violet",
                "folders": ["C:\\...\\Obsidian-Core"], "embedding_model": "chroma-default",
                "created_at": "2026-10-18T12:00:00-03:00",
                "sqlite_path": null, "vector_store_dir": null } ] }
```
- `id`: slug ASCII único derivado do nome.
- `sqlite_path`/`vector_store_dir`: `null` = padrão `data/vaults/<id>/escolio.sqlite3` e
  `data/vaults/<id>/vector_store`. Só a vault migrada aponta para os caminhos antigos.
- `embedding_model`: fixado na criação (os vetores dependem dele); trocar exige reindexar.

## Por vault × global
| Por vault | Global |
|---|---|
| SQLite, Chroma, notas estruturadas, `corpus_roots` | provedor/modelo de IA, voz, microfone, aparência |
| Fila (job leva o runtime da sua vault), Monitorar pasta | modelos de voz baixados (`results/audio`) |
| grafo, tela Notas, conversas | `user_settings.json`, benchmark (corpus temporário) |

`results_dir` continua global (preferências e modelos de voz); a vault troca só `sqlite_path`,
`vector_store_dir` e `notes_dir`.

## Regras
- **Migração:** sem `vaults.json`, o corpus atual vira a vault `obsidian` ("Obsidian", nome da 1ª
  raiz se houver), apontando para os arquivos existentes. Nada é copiado.
- **Troca de vault:** o runtime (SQLite/Chroma/embedder) é refeito para a vault nova; o watcher da
  vault anterior para. Um job em andamento continua na vault dele; um job por vez no app.
- **Excluir vault:** confirma com o nome; apaga `data/vaults/<id>/`, nunca as pastas de origem.
  Não exclui a única vault; excluir a ativa ativa outra.
- **Filtro "Pasta" do chat** continua dentro da vault (várias pastas por vault).

## Fases
1. Backend: registro, `Settings` por vault, troca de runtime no bridge, migração, CLI `vault list|use`.
2. Grafo do corpus + clique abre a nota (em paralelo com a fase 1).
3. Interface: seletor na sidebar, criar vault, aba "Vaults" nas Configurações, Fila com o nome da
   vault, conversas por vault, refresh de tudo ao trocar.
