# Experimento 13 - Validacao exaustiva do ask corpus

## Objetivo

Validar se o fluxo `free-plaud corpus index` + `free-plaud corpus ask` esta funcional em
cenarios multi-documento reais e controlados, incluindo `.md`, `.pdf`, reindexacao,
estrategias `lexical`, `vector` e `hybrid`, perguntas negativas e amostra copiada do Obsidian.

## Senior second pass do pedido

### Verdict

Approved with adjustments.

### Findings

- [P1] O pedido original dizia "testar exaustivamente", mas nao definia matriz de aceite. Isso pode virar teste solto sem conclusao. Correcao: separar a bateria por regressao automatizada, corpus controlado, corpus misto `.md/.pdf`, copia do Obsidian, estrategias, negativos, idempotencia e latencia.
- [P1] Testar direto no vault Obsidian seria risco desnecessario. Correcao: copiar amostra para pasta temporaria e indexar somente a copia.
- [P1] O vault Obsidian nao possui PDFs detectados. Correcao: registrar esse fato e cobrir PDF com corpus controlado gerado e PDFs locais de amostra fora do vault.
- [P2] Multi-documento precisa ser medido por resposta final com `citations`, nao apenas por hits de retrieval. Correcao: contar notas citadas e fontes usadas por pergunta.
- [P2] Validar apenas `hybrid` esconderia diferencas importantes. Correcao: comparar `lexical`, `vector` e `hybrid`.

## Ambiente

- Branch: `feat/corpus-index-and-ask`
- Vault Obsidian: `C:\Users\ricar\OneDrive\Documentos\Obsidian Vault\Obsidian-Core`
- Arquivos no vault:
  - `.md`: 470
  - `.pdf`: 0
- Amostra copiada do Obsidian:
  - `.md`: 15
  - PDFs de controle adicionados na copia: 2
  - PDFs locais de amostra copiados: 2
- Artefatos temporarios:
  - `C:\Users\ricar\AppData\Local\Temp\free-plaud-exhaustive-corpus-yck6cgu8`
  - `C:\Users\ricar\AppData\Local\Temp\free-plaud-cli-exhaustive-f540db1f621b4846a4c99654f74d1281`

## Bateria executada

### 1. Regressao automatizada

```powershell
cd D:\Dev\Repos\Own\tcc-free-plaud\pipeline
uv run pytest --basetemp .pytest-tmp-exhaustive-regression -q
uv run free-plaud --help
uv run free-plaud corpus --help
uv run free-plaud corpus ask --help
```

Resultado:

```text
140 passed in 29.39s
```

### 2. Corpus controlado do projeto

Corpus:

```text
data/results/validation_distributed_corpus
```

Resultado de indexacao:

```json
{
  "status": "success",
  "total_found": 3,
  "indexed_count": 3,
  "failed_count": 0,
  "skipped_count": 0,
  "chunks_first": 3,
  "chunks_second": 3,
  "vector_count_first": 3,
  "vector_count_second": 3,
  "idempotent_counts": true
}
```

Resultado por pergunta:

| Caso | Strategy | Status | Notas citadas | Observacao |
| --- | --- | --- | ---: | --- |
| multi 3 fontes | lexical | `answer` | 3 | OK |
| multi 3 fontes | vector | `answer` | 2 | Limitacao: vector sozinho nao recuperou todas as fontes |
| multi 3 fontes | hybrid | `answer` | 3 | OK |
| single source | lexical/vector/hybrid | `answer` | 1 | OK |
| irrelevante | lexical/vector/hybrid | `no_answer` | 0 | OK |
| anchor ausente | lexical/vector/hybrid | `no_answer` | 0 | OK |
| multi com `top_k=1` | hybrid | `answer` | 1 | OK como parcial; nao inventou 3 fontes |

### 3. Corpus controlado misto `.md/.pdf`

Corpus criado em temp:

- `01_broker.md`
- `02_runbook.pdf`
- `03_padrao.pdf`
- `ignorado.docx`

Resultado de indexacao:

```json
{
  "status": "success",
  "total_found": 3,
  "indexed_count": 3,
  "failed_count": 0,
  "skipped_count": 1,
  "chunks_first": 3,
  "chunks_second": 3,
  "vector_count_first": 3,
  "vector_count_second": 3,
  "idempotent_counts": true
}
```

Resultado por pergunta:

| Caso | Strategy | Status | Notas citadas | Observacao |
| --- | --- | --- | ---: | --- |
| multi `.md + pdf + pdf` | lexical | `answer` | 3 | OK |
| multi `.md + pdf + pdf` | vector | `answer` | 1 | Limitacao: vector sozinho ficou incompleto |
| multi `.md + pdf + pdf` | hybrid | `answer` | 3 | OK |
| pergunta so sobre PDF | lexical/vector/hybrid | `answer` | 1 | OK |
| irrelevante | lexical/vector/hybrid | `no_answer` | 0 | OK |

Smoke CLI real no mesmo corpus:

```json
{
  "index_status": "success",
  "total_found": 3,
  "indexed_count": 3,
  "skipped_count": 1,
  "ask_status": "answer",
  "ask_cited_note_count": 3,
  "negative_status": "no_answer",
  "negative_reason": "citation_validation_failed"
}
```

### 4. Copia do Obsidian + PDFs

Resultado de indexacao:

```json
{
  "status": "success",
  "total_found": 19,
  "indexed_count": 19,
  "failed_count": 0,
  "skipped_count": 0,
  "chunks_first": 294,
  "chunks_second": 294,
  "vector_count_first": 294,
  "vector_count_second": 294,
  "idempotent_counts": true
}
```

Resultado por pergunta:

| Caso | Strategy | Status | Notas citadas | Observacao |
| --- | --- | --- | ---: | --- |
| DHCP + DNS | lexical | `answer` | 1 | Recuperou, mas resposta curta/fraca |
| DHCP + DNS | vector | `answer` | 1 | Recuperou, mas resposta curta/fraca |
| DHCP + DNS | hybrid | `answer` | 1 | Recuperou, mas resposta curta/fraca |
| DHCP + DNS explicito | lexical/vector/hybrid | `answer` | 3 | Stitching ocorreu, mas trouxe stubs/notas proximas |
| Akita + producao | lexical | `answer` | 1 | OK parcial |
| Akita + producao | vector/hybrid | `no_answer` | 0 | Gate de anchor bloqueou |
| Akita + producao explicito | lexical/vector/hybrid | `answer` | 2 | Stitching ocorreu, mas hybrid trouxe nota irrelevante em um caso |
| ContextSnap + Dream Spec | lexical/hybrid | `answer` | 1 | Problema: resposta veio de bloco JS/Dataview |
| ContextSnap + Dream Spec | vector | `no_answer` | 0 | Gate bloqueou evidencia fraca |
| PDF controlado dentro da copia | lexical/vector/hybrid | `answer` | 2 | OK |
| pergunta irrelevante | lexical/vector/hybrid | `no_answer` | 0 | OK |

## Interpretacao tecnica

O fluxo multi-documento esta funcional no sentido de produto minimo:

- indexa pasta recursiva;
- aceita `.md` e `.pdf`;
- ignora extensao nao suportada;
- persiste SQLite e Chroma;
- reindexa sem duplicar contagens;
- responde com multiplas notas citadas;
- mantem `no_answer` para perguntas irrelevantes;
- funciona pela CLI real.

Mas o teste com Obsidian mostra que ainda nao esta pronto para ser vendido como RAG robusto sobre vault real sem uma nova slice:

- notas Obsidian com Dataview/DataviewJS podem virar resposta com codigo (`const title = ...`);
- notas stub muito curtas geram respostas pouco informativas;
- perguntas com `X e Y` nem sempre acionam stitching se nao estiverem formuladas como multiparte explicita;
- `vector` sozinho e instavel para perguntas multi-fonte;
- `hybrid` e melhor default, mas ainda pode puxar nota relacionada errada quando o corpus tem muitos stubs parecidos;
- latencia no corpus Obsidian copiado com 294 chunks ficou na faixa de ~2s a ~12s por pergunta.

## Decisao

Manter `hybrid` como default para `corpus ask`.

Nao promover `vector` sozinho como demo principal de multi-documento.

Antes de ampliar para vault Obsidian real, executar nova slice de limpeza/ranking:

1. filtrar ou limpar blocos Obsidian/Dataview/JS antes do chunking;
2. penalizar chunks compostos majoritariamente por codigo/configuracao;
3. melhorar detecção de pergunta multiparte com enumeração `X e Y`;
4. melhorar ranking por titulo/nome da nota quando pergunta cita entidades que sao titulos;
5. registrar benchmark especifico para Obsidian copiado.

## Proximo passo recomendado

Criar slice `fix/obsidian-corpus-clean-ranking` ou equivalente, com TDD:

- fixture de nota com bloco DataviewJS;
- fixture de nota stub curta;
- fixture de duas notas por titulo (`ContextSnap`, `Dream Spec`);
- teste exigindo que resposta nao contenha `const`, `style.cssText`, `dv.` ou blocos de codigo quando pergunta for conceitual;
- teste exigindo que pergunta `DHCP e DNS` cite as duas notas esperadas sem puxar `VPN`/`VLAN`.
