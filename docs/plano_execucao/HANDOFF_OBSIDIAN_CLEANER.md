# Handoff - Preprocessador seguro de notas Obsidian para ingestao no pipeline

## Objetivo

Criar um preprocessador deterministico que leia arquivos `.md` do Obsidian em modo **somente leitura**,
extraia conteudo textual util de Markdown + `dataviewjs`, e gere `.md` limpo em uma area de staging
dentro deste repositorio, pronto para ser ingerido pelo pipeline atual.

Escopo desta slice:

- ler arquivos `.md` do vault
- nao modificar nenhum arquivo do vault
- limpar links e ruido de Obsidian
- extrair texto util de blocos `dataviewjs`
- salvar output limpo em destino local do repo
- validar no slice Cisco antes de qualquer ampliacao

Nao faz parte desta slice:

- alterar o vault do usuario
- alterar `load_document`, `structure_document`, `search.py`, `runners.py` ou `rag.py`
- usar LLM
- executar JavaScript
- ingerir o vault inteiro

## Baseline real do projeto hoje

Antes de definir esta slice, o comportamento atual do pipeline foi validado diretamente sobre 4 arquivos
crus do slice Cisco, sem qualquer limpeza intermediaria.

Arquivos avaliados:

- `CyberOps.md`
- `CyberOps - SOC.md`
- `CyberOps - Agentes de Ameaça.md`
- `CyberOps - Windows.md`

Achados principais:

1. `load_document()` hoje le `.md` cru como texto puro
2. `structure_document()` nao remove:
   - `dataviewjs`
   - HTML inline
   - CSS inline
   - links `[[...]]`
3. `normalized_text` preserva o JavaScript e o HTML praticamente intactos
4. `summary` pode sair inutil ou enganoso
5. `ask` consegue responder algo em alguns casos, mas a resposta fica poluida com:
   - HTML
   - fragmentos de JS
   - headings errados
   - claims incompletos

Exemplos reais observados:

- `CyberOps.md`
  - `title`: aceitavel
  - `summary`: virou citaçao final de rodape, nao o conteudo principal
- `CyberOps - SOC.md`
  - `summary`: virou `<div align="center">_=date(now)_</div>`
  - `ask "O que e um SOC?"`: respondeu com trecho HTML + fragmento `sub.textContent=...`
- `CyberOps - Agentes de Ameaça.md`
  - `ask "Quais sao os quatro perfis..."`: respondeu so heading + um perfil parcial
- `CyberOps - Windows.md`
  - `ask "O que e ADS no NTFS?"`: respondeu com heading HTML + fragmento de cabecalho JS, nao definicao limpa

Metricas observadas no slice:

- `CyberOps.md`
  - `4` blocos `dataviewjs`
  - `8` links `[[...]]`
- `CyberOps - SOC.md`
  - `6` blocos `dataviewjs`
  - `4` links `[[...]]`
- `CyberOps - Agentes de Ameaça.md`
  - `4` blocos `dataviewjs`
  - `4` links `[[...]]`
- `CyberOps - Windows.md`
  - `10` blocos `dataviewjs`
  - `6` links `[[...]]`

Conclusao do baseline:

> o projeto ja consegue ingerir esses arquivos tecnicamente, mas o resultado sem limpeza fica ruim demais
> para retrieval/answer confiavel.

Portanto esta slice e justificavel.

## Veredito senior sobre plano original

Direcao boa, mas plano original estava arriscado em 5 pontos:

1. misturava leitura e possivel escrita perto demais do vault do usuario
2. tratava `dataviewjs` como se fosse trivial de parsear genericamente
3. nao proibia explicitamente execucao de JavaScript
4. tinha so teste manual, sem testes automatizados do parser
5. nao definia staging seguro dentro do repo

Correcao adotada neste handoff:

- vault vira **fonte read-only**
- output vai para pasta local do repo
- parser de `dataviewjs` sera **estatico e heuristico**, nunca executor
- slice inicial fica restrito a 4 arquivos Cisco
- testes unitarios entram antes de aceitar feature
- cleaner v1 nasce como ferramenta **explicita**, nao como etapa automatica global do pipeline

## Fonte de dados

Vault de origem:

```text
C:\Users\ricar\OneDrive\Documentos\Obsidian Vault\Obsidian-Core
```

Slice inicial obrigatoria:

```text
C:\Users\ricar\OneDrive\Documentos\Obsidian Vault\Obsidian-Core\Área de TI\Estudos\Cisco
```

Arquivos obrigatorios para validacao inicial:

- `CyberOps.md`
- `CyberOps - SOC.md`
- `CyberOps - Agentes de Ameaça.md`
- `CyberOps - Windows.md`

## Regra de seguranca

Esta tarefa **nao deve alterar nada no Obsidian**.

Regras obrigatorias:

1. abrir arquivos do vault apenas para leitura
2. recusar `dest` dentro do vault
3. gerar output apenas dentro do repositorio
4. se `source` e `dest` apontarem para mesmo arquivo, abortar
5. nao criar backup no vault, porque nem escrita deve existir la

Destino sugerido:

```text
data/results/obsidian_cleaner/<slice>/
```

Exemplo:

```text
data/results/obsidian_cleaner/cisco/
```

## Implementacao sugerida

Arquivo:

```text
pipeline/src/free_plaud/ingest/obsidian_cleaner.py
```

Execucao preferida:

```powershell
uv run python -m free_plaud.ingest.obsidian_cleaner <source> <dest>
```

Suporte esperado:

```powershell
# arquivo unico
uv run python -m free_plaud.ingest.obsidian_cleaner "C:\...\CyberOps - SOC.md" "D:\Dev\Repos\Own\tcc-free-plaud\data\results\obsidian_cleaner\cisco\CyberOps - SOC.md"

# diretorio recursivo
uv run python -m free_plaud.ingest.obsidian_cleaner "C:\...\Cisco" "D:\Dev\Repos\Own\tcc-free-plaud\data\results\obsidian_cleaner\cisco"
```

## Contrato da funcao principal

```python
def clean_obsidian_md(source: Path, dest: Path) -> None:
    """
    Le um .md do Obsidian em modo read-only, remove ruido especifico do vault,
    extrai texto util de dataviewjs sem executar JS, e salva markdown limpo
    em destino local do repositorio.
    """
```

## Politica de ativacao

Esta foi a principal correcao de escopo apos medir o baseline real.

### V1

O cleaner **nao** deve rodar sempre.

Ele deve nascer como:

- utilitario explicito
- executado sob demanda
- voltado a arquivos/pastas do Obsidian

Motivo:

1. o pipeline atual ja ingere `.md` comum corretamente
2. nem todo `.md` precisa da perda/transformacao que este cleaner fara
3. rodar sempre aumentaria risco de degradar markdown ja limpo

### Comportamento interno do cleaner

Mesmo sendo explicito, o cleaner deve ter deteccao condicional.

Se arquivo tiver sinais de Obsidian/Dataview, aplicar limpeza forte.

Sinais fortes:

- bloco `````dataviewjs`````
- links `[[...]]`
- navegacao com `←` / `→`
- campos visuais de frontmatter como `banner`, `icon`, `banner-display`
- `createEl(`
- `.style.cssText`
- `dv.container`

Se arquivo **nao** tiver esses sinais:

- passar quase direto
- preservar markdown normal
- remover no maximo ruido minimo configurado, se existir

### Integracao futura

So depois de provar qualidade no slice Cisco, decidir se:

1. continua como ferramenta explicita separada
2. ganha auto-detect dentro da ingestao
3. vira comando oficial `free-plaud obsidian-clean`

Nesta slice, escolha correta e:

> ferramenta explicita + deteccao condicional interna

## Filosofia do parser

### Nao executar JavaScript

`dataviewjs` deve ser tratado como **texto-fonte**, nao como codigo executavel.

Proibido:

- `eval`
- Node
- runtime JS
- Playwright para renderizar pagina
- qualquer execucao do bloco

### Extracao estatica e heuristica

Objetivo:

- extrair valor semantico mais frequente
- nao prometer interpretacao perfeita de qualquer JS arbitrario

Ordem de extracao dentro de cada bloco `dataviewjs`:

1. `textContent = '...'`
2. `textContent = "..." `
3. `innerText = ...`
4. `innerHTML = \`...\``
5. arrays literais de objetos com campos textuais
6. strings longas restantes relevantes

Se estrutura rica nao puder ser reconstruida bem:

- degradar para texto simples
- nao falhar o arquivo inteiro
- registrar warning

## Estruturas-alvo

### 1. Frontmatter YAML

Preservar somente campos semanticos uteis, por exemplo:

- `type`
- `topic`
- `status`
- `tags`
- `created`
- `updated`
- `area`

Descartar campos puramente visuais ou de navegacao, por exemplo:

- `banner`
- `icon`
- `cssclass`
- configuracoes de tema ou layout

### 2. Blocos `dataviewjs`

Extrair:

- texto de `.textContent`
- texto visivel de `innerHTML`
- listas em arrays de objetos
- pares chave/valor semanticos

Converter para markdown simples:

- headings
- subheadings
- listas
- paragrafos

### 3. Markdown normal

Preservar:

- headings
- listas
- texto corrido
- tabelas simples, se existirem

### 4. Links internos Obsidian

Remover completamente:

- `[[...]]`
- navegacao do tipo `← ... | ... →`
- blocos de navegacao que so apontam para outras notas

## Pipeline de limpeza

Executar nesta ordem:

1. ler arquivo em UTF-8
2. separar frontmatter
3. separar blocos `dataviewjs`
4. processar Markdown nao-JS
5. processar `dataviewjs` por extracao estatica
6. remover links internos Obsidian
7. colapsar ruido visual
8. montar markdown final
9. salvar em destino local do repo

## Shape do output

Output deve ser markdown simples, por exemplo:

```markdown
---
type: referencia
topic: cisco
status: em-andamento
tags:
  - area/ti
  - tema/cisco
---

# SOC - Security Operations Center

O SOC e o coracao das operacoes de seguranca...

## O que e um SOC?

Um SOC e uma unidade centralizada...

## Hierarquia e funcoes no SOC

### Nivel 1 - Analista de Alertas

- Monitora alertas recebidos
- Verifica se ocorreu incidente real
```

## Criterios de qualidade

Cada output deve:

1. conter texto util relevante do original
2. nao conter bloco `````dataviewjs`````
3. nao conter `[[`
4. nao conter `.style.cssText`
5. nao conter HTML inline bruto quando texto equivalente puder ser extraido
6. ser markdown legivel
7. ter frontmatter reduzido a campos semanticos
8. ser aceito por `load_document` sem adaptacao extra

## Testes automatizados obrigatorios

Adicionar testes em `pipeline/tests/`.

Cobrir no minimo:

1. arquivo markdown puro passa praticamente intacto
2. frontmatter visual e reduzido para campos semanticos
3. bloco `dataviewjs` com `textContent` vira texto
4. bloco `dataviewjs` com `innerHTML` vira markdown limpo
5. array de objetos vira lista/heading util
6. links `[[...]]` somem
7. `dest` dentro do vault e recusado
8. `dest == source` e recusado
9. arquivo sem sinal de Obsidian quase nao e alterado

Se possivel, usar fixtures pequenas em vez de depender do vault real nos testes.

## Validacao manual obrigatoria

Rodar apenas no slice Cisco.

Para cada um dos 4 arquivos:

1. output existe
2. output tem mais de 200 caracteres
3. nao contem `````dataviewjs`````
4. nao contem `[[`
5. nao contem `.style.cssText`
6. `uv run free-plaud ingest show <arquivo_limpo>` funciona
7. `uv run free-plaud notes build <arquivo_limpo>` funciona

Comparar tambem contra baseline cru:

1. `summary` do arquivo limpo deve ficar melhor que o cru
2. `ask` sobre o arquivo limpo deve ficar mais legivel que o cru
3. resposta nao deve conter:
   - `textContent=`
   - `createEl(`
   - tags HTML inline
   - `.style.cssText`

## Artefatos esperados

Ao final desta sessao:

1. `obsidian_cleaner.py`
2. testes automatizados da limpeza
3. outputs do slice Cisco em `data/results/obsidian_cleaner/cisco/`
4. verificacao manual registrada
5. nenhuma alteracao no vault do Obsidian

## O que nao fazer

- nao escrever nada no vault
- nao mover arquivos do vault
- nao editar plugins/config do Obsidian
- nao executar JS
- nao expandir para vault inteiro nesta rodada
- nao alterar pipeline de retrieval/benchmark
- nao acoplar cleaner ao resto do pipeline nesta slice

## Criterio de aceite

Feature so pode ser aceita se:

1. outputs forem gerados fora do vault
2. 4 arquivos Cisco passarem nos checks manuais
3. testes automatizados cobrirem parser minimo
4. `load_document` e `notes build` aceitarem os arquivos limpos
5. nenhum arquivo do Obsidian for modificado
6. pelo menos `1` pergunta simples por arquivo do slice deve responder melhor no limpo do que no cru

## Proximo passo depois desta slice

So depois de cleaner ficar estavel:

1. decidir se vira comando CLI oficial
2. decidir se entra em fluxo de ingestao batch
3. medir qualidade do markdown limpo em retrieval
