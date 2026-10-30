# 21 - Chunking por segmento de fala (áudio)

## Objetivo

Fazer o áudio transcrito ser fatiado por fala, e não por janela fixa de 800 caracteres, mantendo os tempos
(`t_start`/`t_end`) nos chunks e nas citações.

## Hipótese ou pergunta

- Um chunk que não corta falas no meio e que carrega o tempo de início e fim deve permitir citar o trecho
  exato do áudio.
- NÃO MEDIDO: se o chunking por fala melhora a recuperação (hit@k, MRR) em relação à janela de caracteres.

## Corpus ou suíte usada

- Nenhum corpus de áudio foi usado. Esta máquina não tem Whisper nem as dependências do extra `audio`.
- Os testes usam segmentos sintéticos (`TranscriptSegment`) e o embedder falso de `test_vector_store.py`.
- Arquivo de teste: `pipeline/tests/test_segment_chunking.py` (23 testes).

## Método

1. `load_document` de áudio passa `result.segments` para `IngestedDocument.segments`.
2. `structure_document` usa o texto canônico dos segmentos (`build_segment_text`) como `normalized_text` quando
   há segmentos. Esse texto é os segmentos aparados e unidos por espaço, sem `normalize_text`, porque ele funde
   fragmentos e remove linhas repetidas (por exemplo, "Sim." seguido de "Sim.").
3. `Note.segments` carrega os segmentos só em memória (`exclude=True`, sem persistência).
4. `index_note` usa `chunk_segments` quando a nota tem segmentos e confere que `normalized_text` bate com o
   texto canônico. Sem segmentos, segue `chunk_text` como antes.
5. `chunk_segments`:
   - fecha o chunk ao atingir `target_chars` (800), quando a pausa até a próxima fala passa de `pause_seconds`
     (2.0), ou quando a próxima fala estouraria `max_chars` (1200);
   - fala maior que `max_chars` é dividida por sentença, e sem pontuação por espaço;
   - o tempo de cada pedaço de uma fala dividida é estimado pela proporção de caracteres;
   - IDs são estáveis (`stable_chunk_id` com offsets no texto canônico), `strategy='audio_segments'`.
6. Persistência: SQLite ganha `t_start`/`t_end` (migração com `ALTER TABLE` em `init_sqlite`); Chroma guarda
   os tempos só quando não são nulos; `Citation` ganha `t_start`/`t_end` preenchidos a partir do chunk.

Regressão de texto e PDF: um golden (SHA-256 de chunks de `chunk_text` e de uma nota markdown) foi calculado no
código anterior e continua idêntico. Os campos `t_start`/`t_end` são excluídos desse digest porque são novos.

## Comandos executados

```bash
cd pipeline && uv sync --locked --dev --extra cpu
cd pipeline && uv run ruff check src tests
cd pipeline && uv run pytest -q --deselect tests/test_audio_capture.py
cd pipeline && uv run pytest -q tests/test_segment_chunking.py
```

## Configurações relevantes

| Parâmetro | Valor padrão | Observação |
|---|---|---|
| `target_chars` | 800 | fecha o chunk ao atingir este tamanho |
| `max_chars` | 1200 | limite rígido de tamanho do chunk |
| `pause_seconds` | 2.0 | pausa que força quebra de chunk |
| `chunk_size`, `overlap` | 800, 120 | só registram a configuração do índice (reuso); não controlam o corte |

## Resultados

- `ruff check src tests`: sem erros.
- `pytest tests/test_segment_chunking.py`: 23 testes passando. Cobrem agrupamento, pausa, segmento gigante
  (por frase e sem pontuação), offsets batendo com `normalized_text[char_start:char_end]`, determinismo de IDs,
  regressão de texto (golden), migração de banco SQLite com schema antigo, round-trip SQLite e Chroma com
  tempos, e citação com timestamp.
- Suíte completa (`--deselect tests/test_audio_capture.py`): 699 passando, 10 falhando. As 10 falhas são
  as mesmas que existiam antes da mudança e vêm de dependências do extra `audio` ausentes (`soxr`,
  `ctranslate2`), não do código alterado.
- NÃO MEDIDO: qualquer efeito na qualidade de recuperação ou de resposta com áudio real.
- NÃO MEDIDO: tempo de indexação com transcrições longas.
- NÃO MEDIDO: a precisão dos tempos estimados dentro de falas divididas.

## Interpretação técnica

- A garantia de consistência é estrutural: chunk e nota são derivados do mesmo texto canônico, e a indexação
  falha com `ValueError` se eles divergirem, em vez de gravar offsets errados.
- Notas de áudio mudam de `content_hash` (texto canônico diferente de `normalize_text(result.text)`). Na
  primeira reindexação, áudios antigos serão reprocessados uma vez.
- Notas de áudio sem segmentos (transcrição que não devolve segmentos) seguem o caminho antigo.

## Próximos passos

- Medir recuperação com um corpus de áudio real (hit@k, MRR) comparando `fixed_char_window` e `audio_segments`.
- Decidir se `target_chars`, `max_chars` e `pause_seconds` precisam de calibração.
- Exibir `t_start`/`t_end` na UI (fora do escopo desta mudança).
