# Experimento 20: Benchmark de recuperação reproduzido (substitui a tabela do Experimento 15)

**Data da medição:** 2026-10-31. **Código:** branch `fix/escolio-ollama-validacao` (a partir de `57c9b89`).

## Por que este experimento existe

O Experimento 15 (`15_calibracao_rrf_tcc.md`) declara proveniência não verificada: nenhum script ou saída do repositório gera os números dele. Este experimento refaz a comparação com o próprio harness do app, em um comando reproduzível, e substitui os números do TCC.

## Comando

```bash
cd pipeline
uv run escolio benchmark compare --suite ../data/datasets/manual_validation/suite.json
```

Configuração registrada no JSON da execução: `top_k=3`, `chunk_size=800`, `overlap=120`, `embedding_model=chroma-default`, RRF com `rank_constant=60`, `lexical_weight=1.5`, `vector_weight=1.0`, `lexical_pool=9`, `vector_pool=24`. O provider de resposta foi o `extractive` (padrão), então o experimento mede **só recuperação e abstenção por regra**, sem geração por LLM.

## Suíte

- 10 notas reais (`data/datasets/manual_validation/`), 39 perguntas positivas, 34 negativas por estratégia.
- Perguntas escritas pelo autor do projeto, com gabarito de nota. Não há rotulagem independente.

## Resultados (perguntas positivas, 39)

| Estratégia | MRR | IC 95% (MRR) | Recall@3 | Recall@5 | Latência média por consulta |
|---|---|---|---|---|---|
| Léxica (SQLite FTS5 BM25) | 0.910 | [0.833; 0.962] | 1.000 | 1.000 | 1.2 ms |
| Vetorial (ChromaDB, `chroma-default`) | 0.816 | [0.709; 0.915] | 0.923 | 0.923 | 69 ms |
| Híbrida RRF (k=60, w_lex=1.5) | 0.915 | [0.842; 0.974] | 1.000 | 1.000 | 69 ms |

IC por bootstrap, como gerado pelo `benchmark compare`. A busca léxica e a híbrida chegam a Recall@3 = 1.0, então a comparação entre elas só aparece no MRR.

## Leitura

- A híbrida tem MRR 0.005 acima da léxica, e os intervalos de confiança se sobrepõem quase inteiramente. **Nesta suíte, a fusão não supera a busca léxica de forma distinguível.**
- A híbrida supera a vetorial pura em 0.099 de MRR (+12%), com Recall@3 de 1.0 contra 0.923.
- O custo de latência vem do cálculo de embeddings: vetorial e híbrida ficam em ~69 ms, léxica em ~1 ms.

## Abstenção nas perguntas negativas

Com o provider `extractive`, o benchmark marcou como respondidas **13 de 34** negativas em cada estratégia. A medição foi feita antes e depois das correções de validação deste ciclo, e o número não mudou. Esse valor é alto e contradiz a afirmação de que a regra de abstenção "separa" as negativas. Antes de usar qualquer número de abstenção no TCC, é preciso confirmar o que o campo `answered` mede no benchmark.

## Limitações

- Suíte pequena (10 notas, 39 perguntas). O intervalo do MRR é largo.
- Recall saturado na léxica e na híbrida, então a métrica discrimina pouco entre elas.
- Gabarito feito pelo autor. Sem avaliação independente.
- Os valores de `k` (10, 100) do Experimento 15 não foram remedidos. Mantém-se `k=60` como padrão do projeto, sem reivindicar que seja o ótimo.
- Faithfulness da resposta gerada por LLM não foi medida aqui. A geração com `qchat` foi testada manualmente em 4 perguntas, e a qualidade não foi quantificada.

## Relação com outros experimentos

- Substitui os números de MRR e latência do Experimento 15 em `TCC.md`.
- O Experimento 17 reporta MRR 0.942 para a híbrida em outra passada; não foi reconciliado com este resultado.
