# Handoff - Refinamento visual da TUI Textual

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

Arquivos opcionais, se realmente reduzir complexidade:

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

### 2. Trocar `Select` por toggle segmentado

O `Select` atual e a parte mais feia da tela. Para tres opcoes fixas, usar melhor:

- tres `Button`s pequenos: `lexical`, `vector`, `hybrid`
- classe `.strategy-active` no botao selecionado
- estado interno no `AskPane`

Aceite:

- `hybrid` continua default
- clique em `lexical|vector|hybrid` altera a estrategia
- teste cobre troca de estrategia antes de executar ask

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
- desabilitar enquanto worker roda, se simples

Aceite:

- usuario entende qual acao iniciar
- erro e sucesso voltam o botao para estado normal

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

## Ordem de execucao

1. Criar testes/smokes para visual state:
   - estrategia default `hybrid`
   - clique em estrategia muda valor usado no `ask_file`
   - `run_test(size=(80, 24))` monta sem erro
   - `run_test(size=(120, 36))` monta sem erro
2. Refatorar `AskPane` sem mudar `ask_file`.
3. Aplicar nova estrutura de containers.
4. Reescrever `app.tcss` com foco em sidebar, cards, CTA e estados.
5. Rodar smoke com clique real em `Ask`.
6. Rodar testes.
7. Abrir manualmente `uv run free-plaud-tui` e validar screenshot.

## Validacao

Comandos:

```powershell
cd D:\Dev\Repos\Own\tcc-free-plaud\pipeline
uv run pytest --basetemp .pytest-tmp-tui-visual tests/test_tui_app.py -q
uv run pytest --basetemp .pytest-tmp-full -q
```

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
- `hybrid` ativo visualmente
- `lexical`, `vector`, `hybrid` clicaveis
- campos com card e padding coerente
- botao principal destacado
- empty state de resposta visivel
- resposta real mostra citacoes e latencia
- redimensionamento nao quebra layout

## Branch e commits

Branch sugerida:

```text
feat/tui-visual-polish
```

Commits sugeridos:

```text
test: adicionar smoke visual da tui textual
style: refinar layout da tui textual
docs: registrar plano de refinamento visual da tui
```

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
- nenhum contrato de backend muda
- branch tem commits pequenos e revisaveis
