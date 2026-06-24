import re
import unicodedata
from math import log2

_TOKEN_PATTERN = re.compile(r'[0-9A-Za-zÀ-ÖØ-öø-ÿ]+')

# Stopwords em forma normalizada (sem acento, minúsculas) para o cálculo de
# fundamentação lexical focar em palavras de conteúdo, não em conectivos.
_STOPWORDS_PT = frozenset(
    {
        'a', 'ao', 'aos', 'as', 'com', 'como', 'da', 'das', 'de', 'do', 'dos',
        'e', 'em', 'entre', 'essa', 'esse', 'esta', 'este', 'eu', 'foi', 'isso',
        'ja', 'la', 'mais', 'mas', 'me', 'na', 'nao', 'nas', 'no', 'nos', 'num',
        'numa', 'o', 'os', 'ou', 'para', 'pela', 'pelo', 'por', 'que', 'se',
        'sem', 'ser', 'seu', 'sua', 'tem', 'um', 'uma', 'umas', 'uns',
    }
)


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


def _content_tokens(text: str) -> set[str]:
    """Extrai tokens de conteúdo normalizados (sem acento, sem stopwords)."""
    tokens: set[str] = set()
    for raw in _TOKEN_PATTERN.findall(text):
        folded = unicodedata.normalize('NFKD', raw).encode('ascii', 'ignore').decode('ascii')
        normalized = re.sub(r'[^0-9a-z]+', '', folded.lower())
        if len(normalized) < 2 or normalized in _STOPWORDS_PT:
            continue
        tokens.add(normalized)
    return tokens


def lexical_groundedness(answer: str, supporting_texts: list[str]) -> float:
    """Proxy lexical de faithfulness: fração dos termos de conteúdo da resposta
    que aparecem nos trechos citados.

    Mede ancoragem, não correção: 1.0 indica que todo token informativo da
    resposta tem origem nas evidências recuperadas; valores baixos sinalizam
    afirmações sem suporte no acervo (possível alucinação). Resposta vazia
    retorna 1.0 (não há afirmação a sustentar); evidência vazia com resposta
    não vazia retorna 0.0.
    """
    answer_tokens = _content_tokens(answer)
    if not answer_tokens:
        return 1.0
    support_tokens: set[str] = set()
    for text in supporting_texts:
        support_tokens |= _content_tokens(text)
    if not support_tokens:
        return 0.0
    grounded = answer_tokens & support_tokens
    return len(grounded) / len(answer_tokens)


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
