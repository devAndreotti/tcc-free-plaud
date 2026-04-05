def recall_at_k(relevant_hits: int, total_relevant: int) -> float:
    """Calcula recall simples para o scaffold inicial."""
    if total_relevant <= 0:
        return 0.0
    return relevant_hits / total_relevant
