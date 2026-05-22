# Handoff - Refinamento visual da TUI Textual

## Veredito senior

Status: **aprovado com ajustes**.

O plano esta na direcao certa, mas a primeira versao ainda deixava ambiguidades perigosas para uma IA executar:

- branch base nao estava clara, ja que a TUI atual ainda vive em `feat/tui-textual`
- testes de `run_test` provam montagem, mas nao provam qualidade visual nem ausencia do azul default
- troca de `Select` por botoes precisava de contrato de estado, teclado e teste de valor enviado ao `ask_file`
- estado de execucao do worker precisava bloquear clique duplo e restaurar UI em sucesso/erro
- commit de docs nao deve ser repetido se este handoff ja estiver commitado

Este documento ja incorpora essas correcoes.

## Diagnostico

A TUI atual funciona, mas parece prototipo cru. O problema principal nao e a paleta roxo/rosa em si; e a falta de hierarquia visual.

Problemas vistos no screenshot:

- item selecionado da sidebar cai no azul default do Textual/terminal
- `Select` fica com fundo quase preto e seta default, destoando da paleta
- inputs ocupam largura total demais, criando campos longos e vazios
- painel principal nao tem estrutura de card, header local ou agrupamento claro
- botao parece solto e pequeno perto dos campos
- area de resposta aparece como borda sem empty state util
- footer ocupa espaco, mas nao ajuda o usuario a entender estado/modelo/atalhos
- magenta e roxo aparecem como borda em tudo, entao nada vira destaque real

Conclusao: precisa de uma slice visual focada em layout e componentes de TUI, sem tocar em retrieval, benchmark, embeddings, SQLite ou contrato do `ask_file`.

## Objetivo

Transformar a TUI em uma interface de demo apresentavel no terminal:

- mais bonita em Windows Terminal
- mais legivel em 100x30 e 120x36
- com hierarquia clara entre navegacao, formulario, acao e resposta
- sem default azul do Textual
- sem mudar comportamento do backend

## Escopo permitido

Arquivos principais:

```text
pipeline/src/free_plaud/tui/app.py
pipeline/src/free_plaud/tui/app.tcss
pipeline/tests/test_tui_app.py
```

Arquivos opcionais, se realmente reduzirem complexidade:

```text
pipeline/src/free_plaud/tui/theme.py
pipeline/README.md
```

Nao mexer:

- `pipeline/src/free_plaud/retrieval/*`
- `pipeline/src/free_plaud/benchmark/*`
- `pipeline/src/free_plaud/storage/*`
- datasets
- samples
- frontend React
- Tauri

Regras de branch:

- se `feat/tui-textual` ainda nao foi mergeada em `main`, executar esta slice em cima dela
- se `feat/tui-textual` ja foi mergeada, criar `feat/tui-visual-polish` a partir de `main`
- nao incluir `samples/` se ela estiver untracked

## Direcao visual

Manter roxo/rosa, mas reduzir saturacao global.

Uso recomendado:

- fundo principal quase preto roxo: `#0f0718`
- superficies elevadas: `#180d26`, `#211033`
- borda secundaria: `#372150`
- texto principal: `#f7efff`
- texto secundario: `#bda8cf`
- magenta so para foco/acao: `#f04ddf`
- violeta para selecao ativa: `#7c3aed`
- verde apenas para sucesso: `#6ee7b7`
- amarelo apenas para `no_answer`/alerta: `#fbbf24`
- vermelho apenas para erro: `#fb7185`

Regra: se tudo tem borda magenta, nada tem destaque. Usar magenta apenas em CTA, foco e status ativo.

Regra pratica de TCSS:

- evitar depender de default theme do Textual para selecao
- sobrescrever explicitamente estados `:hover`, `:focus`, `.active` e `.--highlight`
- evitar azul default em `ListView`, `Button`, foco e selecao
- se criar `theme.py`, usar apenas constantes e helpers simples; nao introduzir dependencia nova

## Layout alvo

```text
┌ free-plaud ─────────────────────────────────────────────── 10:16:57 ┐
│                                                                      │
│  free-plaud       │  Ask local                                       │
│  RAG local        │  Consulte um arquivo sem persistir nota          │
│                  │                                                   │
│  > Ask            │  ┌ Arquivo ───────────────────────────────────┐  │
│    Notes          │  │ D:\...\arquivo.md                         │  │
│    Benchmark      │  └────────────────────────────────────────────┘  │
│                  │                                                   │
│  chroma-default   │  Estrategia  [ lexical ] [ vector ] [ hybrid ]   │
│  top_k 5          │                                                   │
│                  │  ┌ Pergunta ──────────────────────────────────┐  │
│                  │  │ O que este documento diz?                  │  │
│                  │  └────────────────────────────────────────────┘  │
│                  │                                                   │
│                  │  [ Executar ask ]                                │
│                  │                                                   │
│                  │  ┌ Resposta ──────────────────────────────────┐  │
│                  │  │ A resposta e citacoes aparecem aqui.        │  │
│                  │  └────────────────────────────────────────────┘  │
│                                                                      │
└ q sair ─ Enter selecionar ─ Tab navegar ─────────────────────────────┘
```

## Mudancas de implementacao

### 0. Baseline antes da alteracao

Antes de editar, registrar evidencias:

```powershell
cd D:\Dev\Repos\Own\tcc-free-plaud
git status --short --branch
cd pipeline
uv run pytest --basetemp .pytest-tmp-tui-before tests/test_tui_app.py -q
```

Abrir manualmente:

```powershell
uv run free-plaud-tui
```

Salvar screenshot ou anotar visualmente:

- azul default aparece na sidebar?
- `Select` ainda parece widget default?
- empty state da resposta existe?
- layout quebra em terminal menor?

Sem esse baseline, a mudanca vira subjetiva demais.

### 1. Sidebar com identidade

Substituir sidebar simples por:

- bloco de marca `free-plaud`
- subtitulo curto `RAG local`
- nav com estados `active`, `hover`, `focus`
- bloco inferior com `embedding_model` e `retrieval_top_k`

Aceite:

- nenhum item selecionado pode ficar azul
- item ativo precisa usar roxo/violeta da paleta
- sidebar deve continuar com largura fixa entre `26` e `30`
- os itens `Notes` e `Benchmark` precisam continuar visivelmente inativos/planejados, nao parecer features prontas

### 2. Trocar `Select` por toggle segmentado

O `Select` atual e a parte mais feia da tela. Para tres opcoes fixas, usar melhor:

- tres `Button`s pequenos: `lexical`, `vector`, `hybrid`
- classe `.strategy-active` no botao selecionado
- estado interno no `AskPane`

Contrato de estado:

- `AskPane` deve manter a estrategia atual em atributo simples, por exemplo `self.selected_strategy`
- `hybrid` deve ser o valor inicial
- clicar em um botao remove `.strategy-active` dos outros e aplica no novo ativo
- `on_button_pressed` do `ask-submit` deve usar `self.selected_strategy`, nao ler texto visual do botao

Aceite:

- `hybrid` continua default
- clique em `lexical|vector|hybrid` altera a estrategia
- teste cobre troca de estrategia antes de executar ask
- navegação por teclado ainda permite chegar nos botoes e no CTA
- se `Button` segmentado ficar ruim no Textual, alternativa aceita: `RadioSet` com TCSS customizado, desde que o azul default tambem suma

### 3. Criar cards no painel principal

Agrupar formulario e resposta em containers:

- `#ask-hero`
- `#ask-form-card`
- `#ask-result-card`

Cada card deve ter:

- fundo levemente mais claro que o background
- borda discreta
- padding consistente
- titulo curto

Aceite:

- campo nao deve parecer jogado direto no fundo
- botao deve estar visualmente associado ao formulario
- resposta deve ter empty state antes da primeira pergunta

### 4. Melhorar CTA

Botao `Executar ask` deve:

- ter cor magenta/violeta forte
- ocupar largura suficiente para parecer acao principal
- mudar estado durante execucao para `Executando...`
- desabilitar enquanto worker roda

Aceite:

- usuario entende qual acao iniciar
- erro e sucesso voltam o botao para estado normal
- clique duplo nao dispara dois workers concorrentes
- erro de arquivo inexistente nao deixa botao travado
- manter `self.app.call_from_thread(...)` em worker; nao voltar para `self.call_from_thread(...)`

### 5. Melhorar resposta e citacoes

Renderizacao atual usa `RichLog` funcional, mas visualmente pobre. Manter `RichLog` se for mais seguro, mas renderizar:

- painel `Resposta`
- bloco `Citacoes`
- bloco `Fontes usadas`
- `latency_ms` como chip discreto
- empty state antes de executar

Aceite:

- `no_answer` aparece em amarelo, com motivo e limitacoes
- resposta com citacao nao mistura tudo em texto solto
- snippets nao quebram layout em 100 colunas
- resposta inicial antes da primeira busca mostra instrucao util, nao caixa vazia
- caminho de fonte longo deve ser encurtado visualmente, sem alterar `Citation.source_path` no backend

### 6. Responsividade minima

Testar estes tamanhos:

```text
80x24
100x30
120x36
```

Aceite:

- sidebar nao invade painel
- card de resposta continua visivel
- formulario nao corta labels essenciais
- em `80x24`, aceitar menos respiro, mas nao aceitar sobreposicao ou overflow inutilizavel

### 7. O que nao deve mudar no comportamento

Esta slice e visual. Portanto:

- `ask_file(...)` deve continuar com mesma assinatura
- `lexical` nao deve inicializar `LocalVectorStore` nem `get_embedder`
- `vector` e `hybrid` continuam inicializando vector store e embedder
- `retrieval_top_k` continua vindo de `Settings`
- `answer_with_citations(...)` nao deve ser alterado
- benchmark nao deve ser alterado

## Ordem de execucao

1. Confirmar branch/status e baseline.
2. Criar testes/smokes para visual state:
   - estrategia default `hybrid`
   - clique em estrategia muda valor usado no `ask_file`
   - clique duplo no CTA nao cria duas chamadas concorrentes
   - erro do worker restaura estado do CTA
   - `run_test(size=(80, 24))` monta sem erro
   - `run_test(size=(100, 30))` monta sem erro
   - `run_test(size=(120, 36))` monta sem erro
3. Refatorar `AskPane` sem mudar `ask_file`.
4. Aplicar nova estrutura de containers.
5. Reescrever `app.tcss` com foco em sidebar, cards, CTA e estados.
6. Rodar smoke com clique real em `Ask`.
7. Rodar testes.
8. Abrir manualmente `uv run free-plaud-tui` e validar screenshot.
9. So entao commitar.

## Validacao

Comandos:

```powershell
cd D:\Dev\Repos\Own\tcc-free-plaud\pipeline
uv run pytest --basetemp .pytest-tmp-tui-visual tests/test_tui_app.py -q
uv run pytest --basetemp .pytest-tmp-full -q
```

Guardrail de retrieval, se qualquer arquivo fora de `tui/` for alterado:

```powershell
cd D:\Dev\Repos\Own\tcc-free-plaud\pipeline
uv run free-plaud benchmark compare `
  --suite "D:\Dev\Repos\Own\tcc-free-plaud\data\datasets\manual_validation\suite.json"
```

Esperado atual:

- `lexical MRR = 0.96875`
- `hybrid MRR = 0.96875`
- `hybrid Recall@3 = 1.0`

Smoke programatico:

```powershell
cd D:\Dev\Repos\Own\tcc-free-plaud\pipeline
@'
import asyncio
from free_plaud.tui.app import FreePlaudApp

async def main():
    for size in ((80, 24), (100, 30), (120, 36)):
        app = FreePlaudApp()
        async with app.run_test(size=size) as pilot:
            await pilot.pause()
            print(f"ok {size}")

asyncio.run(main())
'@ | uv run python -
```

Teste manual:

```powershell
cd D:\Dev\Repos\Own\tcc-free-plaud\pipeline
uv run free-plaud-tui
```

Checklist manual:

- sidebar sem azul default
- foco do teclado tambem sem azul default
- `hybrid` ativo visualmente
- `lexical`, `vector`, `hybrid` clicaveis
- campos com card e padding coerente
- botao principal destacado
- clique duplo no botao nao dispara execucao dupla
- empty state de resposta visivel
- resposta real mostra citacoes e latencia
- redimensionamento nao quebra layout

## Branch e commits

Branch:

```text
se feat/tui-textual nao foi mergeada: continuar em feat/tui-textual
se feat/tui-textual ja foi mergeada: criar feat/tui-visual-polish
```

Commits sugeridos para esta slice:

```text
test: adicionar smoke visual da tui textual
style: refinar layout da tui textual
```

Nao criar novo commit `docs:` se este handoff ja estiver commitado e nao for alterado durante a implementacao.

## Fora de escopo

- file picker nativo
- mouse UX avancada
- tema claro
- animacoes complexas
- tela real de Notes
- tela real de Benchmark
- multi-file ask
- persistencia em SQLite pela TUI

## Criterio de pronto

Slice pronta quando:

- TUI abre sem erro
- screenshot fica apresentavel para demo/TCC
- fluxo Ask continua funcionando
- testes passam
- smoke de tamanhos passa
- nenhum contrato de backend muda
- branch tem commits pequenos e revisaveis
