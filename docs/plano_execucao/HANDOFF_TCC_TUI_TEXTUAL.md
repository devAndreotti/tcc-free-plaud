# Handoff - TUI Textual para `free-plaud`

## Veredito senior

Plano junior estava **direcionalmente util**, mas errado em pontos estruturais:

1. tratava TUI quase como casca trivial
2. assumia assinaturas de backend que **nao batem** com codigo real
3. misturava tela, ingestao, benchmark e consultas SQLite cedo demais
4. queria entregar 3 telas funcionais em 1 rodada sem antes provar um shell minimo
5. trazia paleta verde, mas esta execucao deve usar **roxo + rosa**

Conclusao:

- TUI com Textual faz sentido
- mas precisa nascer em **slices pequenas**
- primeira entrega deve ser um shell TUI com tela `Ask`
- `Notes` e `Benchmark` entram depois

## Contexto real do repo

Backend hoje:

- CLI Python com `Typer`
- RAG heuristico com citacoes
- benchmark reproduzivel
- SQLite + ChromaDB local
- branch principal de trabalho atual focada em backend experimental

Estado validado do retrieval:

- `lexical MRR = 0.96875`
- `vector MRR = 0.7916666666666666`
- `hybrid MRR = 0.96875`
- `hybrid Recall@3 = 1.0`

Observacao importante:

- `ask` atual recebe **`Note` em memoria**
- nao existe hoje um `answer_with_citations(query=..., connection=..., note_id=...)`
- portanto TUI nao deve fingir que existe um fluxo multi-note pronto no backend

## Erros concretos do plano junior

### 1. Contrato errado de `answer_with_citations`

Plano junior propunha:

```python
response = answer_with_citations(
    query=query,
    connection=conn,
    vector_store=vector_store,
    embedder=embedder,
    strategy=strategy,
    note_id=note_id,
)
```

Contrato real hoje:

```python
answer_with_citations(
    note: Note,
    question: str,
    top_k: int = 3,
    *,
    strategy: Literal["lexical", "vector", "hybrid"] = "lexical",
    vector_store: LocalVectorStore | None = None,
    embedder: Embedder | None = None,
    ...
) -> AskResponse
```

Impacto:

- codigo do junior nao rodaria

Correcao:

- TUI v1 deve perguntar sobre **um arquivo carregado na sessao**
- nao sobre `note_id` vindo do banco

### 2. Contrato errado de benchmark

Plano junior assume benchmark rodando em cima de `connection` e `suite` soltos, mas o contrato real precisa de:

- `BenchmarkSuite`
- `workspace_dir`
- `connection`
- `vector_store`
- `embedder`

E o runner principal e:

- `compare_benchmark_suite(...)`

Impacto:

- tela de benchmark e mais cara do que parece
- nao deve entrar na primeira slice

### 3. Ingestao incompleta

Plano junior chama:

- `load_document(path)`
- `structure_document(document)`
- `index_note_in_vector_store(note, vector_store, embedder)`

Mas para ficar coerente com o resto do sistema, `NotesScreen` tambem precisaria:

- persistir nota em SQLite com `upsert_note(...)`
- persistir chunks com `replace_chunks_for_note(...)`

Impacto:

- "ingestao funciona" no plano junior era meia verdade

### 4. Consulta SQL otimista demais

Plano junior usa:

```sql
SELECT note_id, title, source_name, created_at FROM notes ORDER BY created_at DESC
```

Isso ate parece bater com schema atual, mas a tela nao pode nascer assumindo que backend futuro sempre sera SQLite-first para tudo.

Impacto:

- forte acoplamento cedo demais

Correcao:

- primeira slice nao precisa de listagem real de notas persistidas
- pode trabalhar com estado de sessao

### 5. Escopo grande demais

Junior quer entregar:

- shell
- ask
- notes
- ingestao
- benchmark

numa primeira passada.

Impacto:

- alto risco de virar UI quebrada sobre backend sensivel
- alto risco de drift com contratos reais

Correcao:

- slice 1 = shell + Ask
- slice 2 = Notes
- slice 3 = Benchmark

## Objetivo correto

Criar uma TUI **operacional e segura** para demonstracao local do backend, sem quebrar:

- CLI existente
- benchmark atual
- fluxo experimental do TCC

Primeira meta:

- abrir TUI
- carregar arquivo manualmente
- montar `Note`
- perguntar com `lexical|vector|hybrid`
- renderizar resposta, citacoes e `no_answer`

## Escopo da slice 1

Implementar somente:

- estrutura TUI base com Textual
- navegação lateral
- tela `Ask`
- carregamento manual de arquivo
- execucao de `answer_with_citations(...)` usando contratos reais

Nao implementar ainda:

- tela `Notes`
- tela `Benchmark`
- ingestao persistente completa
- listagem via SQLite
- multi-note ask
- execucao de benchmark dentro da TUI

## Paleta - roxo e rosa

Usar esta direcao visual:

```python
SURFACE   = "#12091f"
SURFACE_2 = "#1a0f2d"
SURFACE_3 = "#24143b"

TEXT        = "#f6eefe"
TEXT_MUTED  = "#c7afd9"
TEXT_SUBTLE = "#8f6daa"

ACCENT      = "#d946ef"   # rosa-magenta principal
ACCENT_SOFT = "#a855f7"   # roxo forte secundario

SUCCESS = "#6ee7b7"
DANGER  = "#fb7185"
WARNING = "#fbbf24"
BORDER  = "#4c1d95"
```

## Layout correto

```text
┌──────────────────────────────────────────────┐
│ free-plaud TUI                        [hora] │
├──────────────────┬───────────────────────────┤
│ Navegacao        │ Area principal            │
│                  │                           │
│ > Ask            │ Conteudo dinamico         │
│   Notes          │                           │
│   Benchmark      │                           │
│                  │                           │
├──────────────────┴───────────────────────────┤
│ [↑↓] Navegar  [Enter] Abrir  [q] Sair        │
└──────────────────────────────────────────────┘
```

Regras:

- coluna esquerda fixa em `28`
- painel principal sempre elastico
- nada com largura fixa no conteudo principal

## Arquivos a criar

```text
pipeline/src/free_plaud/tui/__init__.py
pipeline/src/free_plaud/tui/app.py
pipeline/src/free_plaud/tui/app.tcss
```

Adicionar entrypoint real:

```toml
[project.scripts]
free-plaud-tui = "free_plaud.tui.app:main"
```

## Leitura obrigatoria antes de codar

1. `AGENTS.md`
2. `docs/ORDEM_DE_LEITURA_IA.md`
3. `docs/arquitetura/Arquitetura_Backend.md`
4. `pipeline/src/free_plaud/retrieval/rag.py`
5. `pipeline/src/free_plaud/benchmark/runners.py`
6. `pipeline/src/free_plaud/app/config.py`
7. `pipeline/src/free_plaud/storage/sqlite.py`
8. `pipeline/src/free_plaud/retrieval/indexer.py`

## Implementacao correta - Slice 1

### Dependencia

```powershell
cd D:\Dev\Repos\Own\tcc-free-plaud\pipeline
uv add textual
```

### TCSS base

Usar mesma estrutura do plano junior, mas com paleta roxo/rosa:

```css
Screen {
    background: #12091f;
}

Header {
    background: #24143b;
    color: #f6eefe;
    text-style: bold;
}

Footer {
    background: #1a0f2d;
    color: #c7afd9;
}

#nav-panel {
    width: 28;
    border-right: solid #4c1d95;
    background: #1a0f2d;
    padding: 1 0;
}

#nav-title {
    color: #d946ef;
    text-style: bold;
    padding: 0 2 1 2;
}

#main-panel {
    background: #12091f;
    padding: 1 2;
}

ListView {
    background: #1a0f2d;
}

ListView > ListItem {
    color: #f6eefe;
    padding: 0 2;
}

ListView > ListItem.--highlight {
    background: #a855f7 25%;
    color: #f6eefe;
}

ListView:focus > ListItem.--highlight {
    background: #d946ef 40%;
    color: #f6eefe;
}

Input, Select {
    border: solid #4c1d95;
    background: #1a0f2d;
    color: #f6eefe;
}

Input:focus, Select:focus {
    border: solid #d946ef;
}

Button {
    background: #24143b;
    color: #d946ef;
    border: solid #4c1d95;
    margin: 1 0;
}

Button:hover {
    background: #a855f7 20%;
}

Button:focus {
    border: solid #d946ef;
}

.accent  { color: #d946ef; }
.muted   { color: #c7afd9; }
.subtle  { color: #8f6daa; }
.success { color: #6ee7b7; }
.danger  { color: #fb7185; }
.warning { color: #fbbf24; }
.hidden  { display: none; }
```

### App principal

Implementar:

- `NavSelected(Message)`
- `NavPanel`
- `AskScreen`
- `FreePlaudApp`

### Fluxo correto da `AskScreen`

A tela deve pedir:

1. caminho do arquivo
2. estrategia (`lexical`, `vector`, `hybrid`)
3. pergunta

Fluxo:

```python
document = load_document(path)
note = structure_document(document)
vector_store = LocalVectorStore(
    settings.vector_store_dir,
    collection_name=settings.vector_collection_name,
)
embedder = get_embedder(settings.embedding_model)

response = answer_with_citations(
    note,
    question,
    strategy=strategy,
    vector_store=vector_store,
    embedder=embedder,
)
```

Observacao:

- para `lexical`, `vector_store` e `embedder` podem continuar sendo passados ou tratados condicionalmente
- nao usar subprocess
- nao inventar camada de service se nao for necessario nesta primeira slice

### Renderizacao correta

Se `response.no_answer`:

- painel amarelo
- mostrar `reason_for_no_answer`
- mostrar `limitations`

Se `response.status == "answer"`:

- painel principal com `response.answer`
- tabela/lista de `citations`
- opcional: mostrar `used_sources`

## Slices seguintes

### Slice 2 - `Notes`

So depois da tela `Ask` estavel.

Entram:

- persistencia em SQLite
- `upsert_note(...)`
- `replace_chunks_for_note(...)`
- listagem de `notes`

### Slice 3 - `Benchmark`

So depois de `Ask` e `Notes`.

Entram:

- input de `suite.json`
- `compare_benchmark_suite(...)`
- tabela de `MRR`, `Recall@3`, `latencia`

## O que nao fazer

- nao mexer em `free-plaud` CLI existente
- nao mudar contratos de `rag.py`
- nao acoplar TUI a schema SQL em toda parte
- nao abrir multi-file ask nesta rodada
- nao misturar frontend React com TUI Textual
- nao alterar benchmark para atender UI

## Validacao correta

### Smoke

```powershell
cd D:\Dev\Repos\Own\tcc-free-plaud\pipeline
uv run free-plaud-tui
```

### Guardrail benchmark

```powershell
cd D:\Dev\Repos\Own\tcc-free-plaud\pipeline
uv run free-plaud benchmark compare `
  --suite "D:\Dev\Repos\Own\tcc-free-plaud\data\datasets\manual_validation\suite.json"
```

Esperado:

- numeros iguais aos atuais

### Testes

```powershell
cd D:\Dev\Repos\Own\tcc-free-plaud\pipeline
$tmp = "D:\Dev\Repos\Own\tcc-free-plaud\.pytest-tmp-$([guid]::NewGuid().ToString())"
uv run pytest --basetemp $tmp -q
```

Esperado:

- suite verde depois de adicionar `textual`

### Teste manual minimo da slice 1

1. abrir TUI
2. apontar arquivo real
3. perguntar com `lexical`
4. perguntar com `hybrid`
5. ver `citations`
6. redimensionar terminal
7. confirmar que layout nao quebra

## Branch e commits sugeridos

Branch:

- `feat/tui-textual`

Commits:

1. `feat: adicionar shell inicial da tui textual`
2. `feat: adicionar tela ask da tui textual`
3. `docs: registrar handoff da tui textual`

## Critério de sucesso da slice 1

- `uv run free-plaud-tui` abre
- paleta roxo/rosa aplicada
- resize nao quebra layout
- usuario consegue apontar arquivo manualmente
- `AskScreen` chama `answer_with_citations(...)` com contrato real
- resposta e `no_answer` aparecem formatados
- benchmark e testes existentes continuam estaveis

## Proximo passo depois desta slice

Se a slice 1 fechar:

- abrir handoff separado para `Notes`
- depois handoff separado para `Benchmark`

Nao tentar entregar tudo de uma vez.
