from math import log2

import pytest

from free_plaud.benchmark.metrics import (
    abstention_metrics,
    bootstrap_ci,
    lexical_groundedness,
    ndcg_at_k,
)


def test_ndcg_rewards_relevant_hits_near_the_top() -> None:
    assert ndcg_at_k([1, 1, 1], 10) == pytest.approx(1.0)
    # rank 2 vale 1/log2(3); rank 3 vale 1/log2(4); miss vale 0.
    expected = ((1 / log2(3)) + (1 / log2(4)) + 0.0) / 3
    assert ndcg_at_k([2, 3, None], 10) == pytest.approx(expected)


def test_ndcg_ignores_hits_beyond_k_and_handles_empty() -> None:
    assert ndcg_at_k([4], 3) == 0.0
    assert ndcg_at_k([], 10) == 0.0
    assert ndcg_at_k([1], 0) == 0.0


def test_ndcg_discounts_lower_ranks_more_than_recall() -> None:
    top = ndcg_at_k([1], 10)
    deep = ndcg_at_k([5], 10)
    assert top == pytest.approx(1.0)
    assert 0.0 < deep < top


def test_lexical_groundedness_full_partial_and_edges() -> None:
    sources = ['O benchmark mede recall e latência no ChromaDB local.']
    assert lexical_groundedness('O benchmark mede recall.', sources) == pytest.approx(1.0)

    partial = lexical_groundedness('O benchmark usa Pinecone remoto.', sources)
    assert 0.0 < partial < 1.0

    # Resposta vazia: nada a sustentar.
    assert lexical_groundedness('', sources) == 1.0
    # Resposta sem evidência citada: nada pode sustentá-la.
    assert lexical_groundedness('Qualquer afirmação relevante aqui.', []) == 0.0


def test_lexical_groundedness_ignores_accents_and_stopwords() -> None:
    # 'citação' deve casar com 'citacao'; stopwords não contam como conteúdo.
    score = lexical_groundedness('A citação é obrigatória.', ['Citacao obrigatoria no RAG.'])
    assert score == pytest.approx(1.0)


def test_abstention_metrics_perfect_and_mixed() -> None:
    perfect = abstention_metrics([True, False, True], [True, False, True])
    assert perfect['accuracy'] == pytest.approx(1.0)
    assert perfect['precision'] == pytest.approx(1.0)
    assert perfect['recall'] == pytest.approx(1.0)
    assert perfect['f1'] == pytest.approx(1.0)
    assert perfect['support'] == 3.0

    # tp=1 (idx0), fp=1 (idx1, respondível mas absteve), fn=1 (idx2, devia abster).
    mixed = abstention_metrics([True, True, False], [True, False, True])
    assert mixed['accuracy'] == pytest.approx(1 / 3)
    assert mixed['precision'] == pytest.approx(0.5)
    assert mixed['recall'] == pytest.approx(0.5)
    assert mixed['f1'] == pytest.approx(0.5)


def test_abstention_metrics_empty_and_length_guard() -> None:
    empty = abstention_metrics([], [])
    assert empty == {'support': 0.0, 'accuracy': 0.0, 'precision': 0.0, 'recall': 0.0, 'f1': 0.0}

    with pytest.raises(ValueError):
        abstention_metrics([True], [True, False])


def test_bootstrap_ci_brackets_mean_and_is_deterministic() -> None:
    values = [1.0, 0.5, 0.0, 0.5, 1.0, 0.0, 0.5, 1.0]

    first = bootstrap_ci(values, seed=7)
    second = bootstrap_ci(values, seed=7)

    assert first == second  # mesma seed => resultado idêntico
    assert first['lower'] <= first['mean'] <= first['upper']
    assert first['mean'] == pytest.approx(sum(values) / len(values))
    # Valores em [0,1] => limites também ficam em [0,1].
    assert 0.0 <= first['lower'] <= 1.0
    assert 0.0 <= first['upper'] <= 1.0


def test_bootstrap_ci_no_variance_collapses_interval() -> None:
    constant = bootstrap_ci([0.5, 0.5, 0.5, 0.5])
    assert constant['lower'] == pytest.approx(0.5)
    assert constant['upper'] == pytest.approx(0.5)


def test_bootstrap_ci_handles_empty_and_singleton() -> None:
    assert bootstrap_ci([]) == {'mean': 0.0, 'lower': 0.0, 'upper': 0.0, 'confidence': 0.95}

    singleton = bootstrap_ci([0.8])
    assert singleton['mean'] == pytest.approx(0.8)
    assert singleton['lower'] == pytest.approx(0.8)
    assert singleton['upper'] == pytest.approx(0.8)
