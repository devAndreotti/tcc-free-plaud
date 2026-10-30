import random
from math import log2
from statistics import fmean

# Tokenização e fundamentação lexical vivem em escolio.text_tokens (sem dependência
# da camada de benchmark). Os nomes abaixo são reexportados por compatibilidade.
from escolio.text_tokens import STOPWORDS_PT as _STOPWORDS_PT  # noqa: F401
from escolio.text_tokens import content_tokens as _content_tokens  # noqa: F401
from escolio.text_tokens import lexical_groundedness  # noqa: F401


def recall_at_k(relevant_hits: int, total_relevant: int) -> float:
    """Mantém compatibilidade com o scaffold inicial."""
    if total_relevant <= 0:
        return 0.0
    return relevant_hits / total_relevant


def mean_reciprocal_rank(ranks: list[int | None]) -> float:
    """Calcula MRR usando rank 1-based; queries sem hit contam como zero."""
    if not ranks:
        return 0.0
    return sum((1 / rank) if rank else 0.0 for rank in ranks) / len(ranks)


def recall_at_k_from_ranks(ranks: list[int | None], k: int) -> float:
    """Calcula a fração de queries com pelo menos um hit relevante até k."""
    if not ranks:
        return 0.0
    return sum(1 for rank in ranks if rank is not None and rank <= k) / len(ranks)


def ndcg_at_k(ranks: list[int | None], k: int) -> float:
    """Calcula nDCG@k para relevância binária com um alvo por consulta.

    Cada consulta tem no máximo um trecho relevante, então o ganho ideal
    (IDCG) vale sempre 1.0 (alvo na primeira posição) e o nDCG da consulta
    reduz-se ao ganho com desconto logarítmico do rank. Diferente do
    Recall@k, premia o sistema por colocar o trecho relevante mais ao topo.
    Consultas sem hit até k contribuem com zero.
    """
    if not ranks or k <= 0:
        return 0.0
    total = sum(1.0 / log2(rank + 1) for rank in ranks if rank is not None and rank <= k)
    return total / len(ranks)


def abstention_metrics(
    predicted_abstain: list[bool],
    gold_abstain: list[bool],
) -> dict[str, float]:
    """Avalia a decisão de abster-se ('sem base no acervo') por consulta.

    Trata abster-se como a classe positiva: para perguntas negativas (sem
    resposta no corpus) o sistema deveria abster-se, e para perguntas
    respondíveis deveria responder. Retorna accuracy, precision, recall e f1
    dessa decisão, mais o número de consultas avaliadas em ``support``.
    """
    if len(predicted_abstain) != len(gold_abstain):
        raise ValueError('predicted_abstain e gold_abstain devem ter o mesmo tamanho.')
    total = len(predicted_abstain)
    if total == 0:
        return {'support': 0.0, 'accuracy': 0.0, 'precision': 0.0, 'recall': 0.0, 'f1': 0.0}

    true_positive = false_positive = false_negative = true_negative = 0
    for predicted, gold in zip(predicted_abstain, gold_abstain):
        if predicted and gold:
            true_positive += 1
        elif predicted and not gold:
            false_positive += 1
        elif not predicted and gold:
            false_negative += 1
        else:
            true_negative += 1

    accuracy = (true_positive + true_negative) / total
    precision = true_positive / (true_positive + false_positive) if (true_positive + false_positive) else 0.0
    recall = true_positive / (true_positive + false_negative) if (true_positive + false_negative) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return {
        'support': float(total),
        'accuracy': accuracy,
        'precision': precision,
        'recall': recall,
        'f1': f1,
    }


def bootstrap_ci(
    values: list[float],
    *,
    confidence: float = 0.95,
    iterations: int = 1000,
    seed: int = 0,
) -> dict[str, float]:
    """Intervalo de confiança bootstrap (percentil) para a média de uma métrica.

    Recebe os valores por consulta (ex.: reciprocal rank de cada query),
    reamostra com reposição ``iterations`` vezes e retorna média e limites
    inferior/superior no nível de confiança dado. Determinístico via ``seed``,
    sem dependências externas. Serve para reportar ``MRR 0.62 [0.54, 0.71]`` em
    vez de número solto — relevante quando o dataset é pequeno.
    """
    if not values:
        return {'mean': 0.0, 'lower': 0.0, 'upper': 0.0, 'confidence': confidence}
    if len(values) == 1:
        only = float(values[0])
        return {'mean': only, 'lower': only, 'upper': only, 'confidence': confidence}

    rng = random.Random(seed)
    sample_size = len(values)
    resampled_means = [
        fmean(values[rng.randrange(sample_size)] for _ in range(sample_size)) for _ in range(iterations)
    ]
    resampled_means.sort()
    alpha = (1.0 - confidence) / 2.0
    lower_index = int(alpha * iterations)
    upper_index = min(int((1.0 - alpha) * iterations), iterations - 1)
    return {
        'mean': fmean(values),
        'lower': resampled_means[lower_index],
        'upper': resampled_means[upper_index],
        'confidence': confidence,
    }
