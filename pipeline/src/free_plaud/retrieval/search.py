from free_plaud.retrieval.models import Chunk


def lexical_search(query: str, chunks: list[Chunk], top_k: int = 5) -> list[Chunk]:
    """Busca lexical simples para manter o scaffold funcional sem store vetorial real."""
    normalized = {term.lower() for term in query.split() if term.strip()}
    if not normalized:
        return chunks[:top_k]

    scored = []
    for chunk in chunks:
        haystack = chunk.chunk_text.lower()
        score = sum(1 for term in normalized if term in haystack)
        scored.append((score, chunk.chunk_index, chunk))

    ranked = sorted(scored, key=lambda item: (-item[0], item[1]))
    return [chunk for score, _, chunk in ranked if score > 0][:top_k]
