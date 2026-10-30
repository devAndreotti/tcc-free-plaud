"""Execução do `benchmark compare` com as flags opcionais: ablação do reranker e cobertura.

Fica fora do cli.py: o comando só registra as opções e chama `executar_compare_com_flags`. Sem
nenhuma flag, a função chama `comparar` uma vez com o mesmo reranker de antes e não monta blocos.
"""

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from escolio.benchmark.compare_blocks import (
    bloco_cobertura,
    bloco_faithfulness,
    bloco_reranqueado,
    estrategia_de_referencia,
    intervalos_mrr,
)
from escolio.benchmark.coverage import parse_ks
from escolio.benchmark.datasets import BenchmarkSuite
from escolio.benchmark.faithfulness import FaithfulnessReport
from escolio.benchmark.json_merge import mesclar_chaves_json, verificar_comparacao
from escolio.benchmark.runner_models import (
    CORPUS_RETRIEVAL_DEPTH,
    BenchmarkComparisonResult,
    BenchmarkCorpusResult,
)
from escolio.retrieval.rerank import Reranker


def _corpus(resultado: BenchmarkComparisonResult) -> BenchmarkCorpusResult:
    if resultado.corpus is None:
        raise ValueError('O compare não tem a passada no corpus; sem ela não há bloco para esta flag.')
    return resultado.corpus


def validar_flags_compare(*, com_baseline: bool, rerank_model: str | None, cobertura: str | None) -> list[int] | None:
    """Confere as flags novas antes de abrir o SQLite. Devolve os k da cobertura, ou None sem a flag.

    Erro de uso vira ValueError com a mensagem para o usuário; a CLI converte em BadParameter.
    """
    if com_baseline and not (rerank_model or '').strip():
        raise ValueError('--com-baseline exige --rerank-model (o reranker da segunda passada).')
    if not cobertura:
        return None
    try:
        ks = parse_ks(cobertura)
    except ValueError as exc:
        raise ValueError(f'--cobertura {exc}') from None
    if ks[-1] > CORPUS_RETRIEVAL_DEPTH:
        raise ValueError(f'--cobertura passa da profundidade do corpus ({CORPUS_RETRIEVAL_DEPTH}).')
    return ks


def executar_compare_com_flags(
    suite: BenchmarkSuite,
    *,
    comparar: Callable[..., BenchmarkComparisonResult],
    reranker: Reranker | None,
    rerank_model: str | None,
    com_baseline: bool,
    ks: Sequence[int] | None,
    **kwargs: Any,
) -> tuple[BenchmarkComparisonResult, dict[str, Any]]:
    """Roda `comparar` uma ou duas vezes e devolve (resultado principal, chaves extras do JSON).

    Com `com_baseline`, a primeira passada é sem reranker e vira o resultado principal; a segunda usa
    `reranker` e vira o bloco `reranked`, com `baseline_ci` do principal. `kwargs` leva tudo que
    `compare_benchmark_suite` recebe, inclusive `workspace_dir`, que a cobertura também usa.
    """
    extras: dict[str, Any] = {}
    if com_baseline:
        if reranker is None or not rerank_model:
            raise ValueError('--com-baseline exige --rerank-model com um reranker carregado.')
        principal = comparar(suite, reranker=None, **kwargs)
        com_reranker = comparar(suite, reranker=reranker, **kwargs)
        extras['reranked'] = bloco_reranqueado(rerank_model, _corpus(com_reranker))
        extras['baseline_ci'] = intervalos_mrr(_corpus(principal))
    else:
        principal = comparar(suite, reranker=reranker, **kwargs)
    if ks:
        extras['coverage'] = bloco_cobertura(
            principal,
            suite,
            kwargs['workspace_dir'],
            ks,
            estrategia_de_referencia(principal),
        )
    return principal, extras


def gravar_faithfulness(
    relatorio: FaithfulnessReport,
    comparacao: BenchmarkComparisonResult,
    *,
    saida: Path,
    mesclar_em: Path | None,
    estrategia: str | None,
) -> dict[str, Any]:
    """Grava o relatório em `saida` e, com `mesclar_em`, a chave `faithfulness` no JSON do compare.

    Tudo o que pode falhar (estratégia sem resposta, JSON de outra comparação) é checado antes de
    qualquer escrita, então um erro não deixa `saida` gravado com o compare intocado.
    Erros devolvem ValueError com a mensagem para o usuário.
    """
    bloco = None
    if mesclar_em is not None:
        bloco = bloco_faithfulness(relatorio, estrategia or estrategia_de_referencia(comparacao))
        verificar_comparacao(mesclar_em, relatorio.source_comparison_id)
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text(relatorio.model_dump_json(indent=2) + '\n', encoding='utf-8', newline='\n')
    payload: dict[str, Any] = {'ok': True, 'saida': str(saida)}
    if mesclar_em is not None and bloco is not None:
        mesclar_chaves_json(mesclar_em, {'faithfulness': bloco}, comparison_id=relatorio.source_comparison_id)
        payload['mesclado_em'] = str(mesclar_em)
    return payload
