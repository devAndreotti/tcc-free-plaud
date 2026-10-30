"""Blocos opcionais do JSON do `benchmark compare`: ablação do reranker, cobertura e faithfulness.

Cada função monta uma chave que a UI lê (`UI/src/services/bridge.ts`: BenchmarkReranked,
BenchmarkMrrInterval, BenchmarkCoverage, BenchmarkFaithfulness). Os nomes das chaves seguem esses
tipos. Sem as flags correspondentes, nenhuma destas funções é chamada.

Duas escolhas de leitura da UI, para que os números batam com o painel:
- `single_chunk` e `across_chunks` são contagens de perguntas (a UI divide por `n`), não frações.
- Os blocos de uma estratégia só (cobertura, faithfulness) usam `default_ask_strategy`, a estratégia
  do chat, como o painel já faz para a decisão de abstenção. Sem snapshot, cai em `hybrid`.
"""

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from escolio.benchmark.coverage import (
    build_coverage_row,
    coverage_summary,
    grupo_da_pergunta,
    trechos_do_ranking,
)
from escolio.benchmark.datasets import BenchmarkSuite, load_benchmark_dataset
from escolio.benchmark.faithfulness import FaithfulnessReport
from escolio.benchmark.metrics import bootstrap_ci
from escolio.benchmark.runner_models import (
    BenchmarkComparisonResult,
    BenchmarkCorpusResult,
)
from escolio.ingest.loaders import load_document
from escolio.notes.structurer import structure_document

ESTRATEGIA_PADRAO = 'hybrid'
GRUPO_TODOS = 'todos'
ROTULOS_GRUPO = {
    'unica': 'Um trecho basta',
    'mt-nota': 'Dois trechos da mesma nota',
    'mt-notas': 'Trechos de notas diferentes',
    GRUPO_TODOS: 'Todas as perguntas',
}
DICAS_GRUPO = {
    'unica': 'pergunta de um trecho',
    'mt-nota': 'termos em trechos distantes',
    'mt-notas': 'termos em duas notas',
    GRUPO_TODOS: 'todos os grupos',
}


def estrategia_de_referencia(comparacao: BenchmarkComparisonResult) -> str:
    """Estratégia do chat gravada no compare (`default_ask_strategy`); `hybrid` quando não há snapshot."""
    snapshot = comparacao.settings_snapshot
    return snapshot.default_ask_strategy if snapshot is not None else ESTRATEGIA_PADRAO


def intervalos_mrr(corpus: BenchmarkCorpusResult) -> dict[str, dict[str, float]]:
    """IC 95% bootstrap do MRR por estratégia, sobre o reciprocal rank de cada pergunta positiva.

    Usa os mesmos registros de `corpus.queries` que geram `summaries[...].mrr`; as negativas ficam de fora.
    """
    intervalos: dict[str, dict[str, float]] = {}
    for estrategia, linhas in corpus.queries.items():
        positivas = [linha.reciprocal_rank for linha in linhas if linha.category != 'negativa']
        ic = bootstrap_ci(positivas)
        intervalos[estrategia] = {'mrr_lower': ic['lower'], 'mrr_upper': ic['upper']}
    return intervalos


def bloco_reranqueado(modelo: str, corpus_com_reranker: BenchmarkCorpusResult) -> dict[str, Any]:
    """`reranked`: o reranker só atua na passada no corpus, então os resumos são dela."""
    return {
        'model': modelo,
        'summaries': {nome: resumo.model_dump(mode='json') for nome, resumo in corpus_com_reranker.summaries.items()},
        'ci': intervalos_mrr(corpus_com_reranker),
    }


def termos_e_textos_da_suite(suite: BenchmarkSuite, workspace: Path) -> tuple[dict[str, list[str]], dict[str, str]]:
    """Termos esperados por pergunta positiva e texto normalizado de cada nota, para reconstruir os trechos."""
    textos_por_nota: dict[str, str] = {}
    termos: dict[str, list[str]] = {}
    for case in suite.cases:
        note = structure_document(load_document(workspace / case.document_path))
        # Mesmo texto que chunk_text fatia: normalized_text com strip().
        textos_por_nota[note.note_id] = note.normalized_text.strip()
        for sample in load_benchmark_dataset(workspace / case.dataset_path).samples:
            if sample.category != 'negativa' and sample.expected_terms:
                termos[sample.sample_id] = list(sample.expected_terms)
    return termos, textos_por_nota


def bloco_cobertura(
    comparacao: BenchmarkComparisonResult,
    suite: BenchmarkSuite,
    workspace: Path,
    ks: Sequence[int],
    estrategia: str,
) -> dict[str, Any]:
    """`coverage`: uma profundidade (a maior de `ks`, que é a que a UI mostra) e os grupos da estratégia.

    `single_chunk` conta as perguntas com a régua antiga (um trecho com todos os termos e da nota certa
    dentro do top-k). `across_chunks` conta as perguntas em que a união do top-k cobre todos os termos.
    Ambas saem de `coverage_summary`, sobre a passada no corpus.
    """
    corpus = comparacao.corpus
    if corpus is None:
        raise ValueError('O compare não tem a passada no corpus; a cobertura precisa dela.')
    kmax = max(ks)
    if kmax > corpus.retrieval_depth:
        raise ValueError(f'k={kmax} passa da profundidade gravada no compare ({corpus.retrieval_depth}).')
    termos, textos_por_nota = termos_e_textos_da_suite(suite, workspace)

    linhas = []
    posicao_relevante: dict[str, int | None] = {}
    for nome, perguntas in corpus.queries.items():
        for pergunta in perguntas:
            if pergunta.sample_id not in termos:
                continue  # negativas e amostras fora da suite
            trechos = trechos_do_ranking(pergunta.retrieved, textos_por_nota)
            linhas.append(build_coverage_row(nome, pergunta.sample_id, termos[pergunta.sample_id], trechos, ks))
            if nome == estrategia:
                posicao_relevante[pergunta.sample_id] = pergunta.relevant_rank

    celulas = [
        celula
        for celula in coverage_summary(linhas)
        if celula['strategy'] == estrategia and celula['k'] == kmax
    ]
    grupos = []
    for celula in celulas:
        grupo = str(celula['grupo'])
        n = int(celula['n'])
        across = round(float(celula['juncao_completa']['mean']) * n)  # média de 0/1 vezes n = contagem
        single = sum(
            1
            for sample_id, rank in posicao_relevante.items()
            if (grupo == GRUPO_TODOS or grupo_da_pergunta(sample_id) == grupo) and rank is not None and rank <= kmax
        )
        grupos.append(
            {
                'id': grupo,
                'label': ROTULOS_GRUPO.get(grupo, grupo),
                'hint': DICAS_GRUPO.get(grupo, ''),
                'n': n,
                'single_chunk': single,
                'across_chunks': across,
            }
        )
    return {'k': kmax, 'groups': grupos}


def bloco_faithfulness(relatorio: FaithfulnessReport, estrategia: str) -> dict[str, Any]:
    """`faithfulness`: score, IC 95% e contagens de uma estratégia do relatório do juiz."""
    por_estrategia = relatorio.strategies.get(estrategia)
    if por_estrategia is None:
        raise ValueError(f'estratégia {estrategia!r} não está no relatório de faithfulness.')
    if por_estrategia.faithfulness is None:
        raise ValueError(f'não há respostas para julgar em {estrategia!r}; gere o compare com --registrar-respostas.')
    ic = por_estrategia.faithfulness
    return {
        'score': ic['mean'],
        'ci_lower': ic['lower'],
        'ci_upper': ic['upper'],
        'claims': por_estrategia.claim_count,
        'unparsed': por_estrategia.unparsed_count,
        'judge_model': relatorio.judge_model,
    }
