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
