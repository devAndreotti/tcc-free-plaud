from escolio.notes.schemas import Note
from escolio.providers.answer_quality import contains_token_sequence
from escolio.retrieval.models import SearchHit
from escolio.retrieval.search import STOPWORDS, TOKEN_PATTERN

SHORT_ANCHOR_MAX_LENGTH = 3
SHORT_ANCHOR_EXACT_BOOST = 1.0
SHORT_ANCHOR_TAIL_BOOST = 0.6
SHORT_ANCHOR_CONFLICT_PENALTY = 0.8


def _normalized_anchor_tokens(text: str) -> list[str]:
    return [token.casefold() for token in TOKEN_PATTERN.findall(text)]


def _has_conflicting_short_anchor(tokens: list[str], prefix: list[str], expected_anchor: str) -> bool:
    if not prefix:
        return False
    width = len(prefix) + 1
    for index in range(len(tokens) - width + 1):
        if tokens[index : index + len(prefix)] != prefix:
            continue
        candidate = tokens[index + len(prefix)]
        if (
            candidate != expected_anchor
            and 0 < len(candidate) <= SHORT_ANCHOR_MAX_LENGTH
            and candidate not in STOPWORDS
        ):
            return True
    return False


def _short_anchor_sequences(question: str) -> list[list[str]]:
    tokens = TOKEN_PATTERN.findall(question)
    normalized = [token.casefold() for token in tokens]
    sequences: list[list[str]] = []
    for index, token in enumerate(tokens):
        anchor = token.casefold()
        if len(anchor) > SHORT_ANCHOR_MAX_LENGTH or anchor in STOPWORDS:
            continue
        if not (token.isupper() or any(char.isdigit() for char in token)):
            continue

        previous_terms = [
            normalized[item]
            for item in range(max(0, index - 2), index)
            if len(normalized[item]) >= 4 and normalized[item] not in STOPWORDS
        ]
        if not previous_terms:
            continue

        for width in range(1, len(previous_terms) + 1):
            sequence = [*previous_terms[-width:], anchor]
            if sequence not in sequences:
                sequences.append(sequence)
    return sequences


def _anchor_evidence_tokens(hit: SearchHit, note: Note | None) -> list[str]:
    parts = [hit.chunk.note_id, hit.chunk.chunk_text]
    if note is not None:
        parts.extend([note.title, note.source_name, str(note.source_path)])
    return _normalized_anchor_tokens('\n'.join(part for part in parts if part))


def _short_anchor_score_delta(question: str, hit: SearchHit, note: Note | None) -> float:
    sequences = _short_anchor_sequences(question)
    if not sequences:
        return 0.0

    evidence_tokens = _anchor_evidence_tokens(hit, note)
    delta = 0.0
    for sequence in sequences:
        if contains_token_sequence(evidence_tokens, sequence):
            delta += SHORT_ANCHOR_EXACT_BOOST
        elif len(sequence) > 2 and contains_token_sequence(evidence_tokens, sequence[-2:]):
            delta += SHORT_ANCHOR_TAIL_BOOST

        if _has_conflicting_short_anchor(evidence_tokens, sequence[:-1], sequence[-1]):
            delta -= SHORT_ANCHOR_CONFLICT_PENALTY
    return delta


def _rerank_hits_by_short_anchor(question: str, hits: list[SearchHit], note_lookup: dict[str, Note]) -> list[SearchHit]:
    if not hits or not _short_anchor_sequences(question):
        return hits

    ranked_rows: list[tuple[float, float, int, int, SearchHit]] = []
    for original_index, hit in enumerate(hits):
        note = note_lookup.get(hit.chunk.note_id)
        delta = _short_anchor_score_delta(question, hit, note)
        reranked_hit = hit.model_copy(update={'score': hit.score + delta}) if delta else hit
        ranked_rows.append(
            (reranked_hit.score, reranked_hit.term_coverage, len(reranked_hit.matched_terms), original_index, reranked_hit)
        )

    return [
        row[-1]
        for row in sorted(
            ranked_rows,
            key=lambda item: (-item[0], -item[1], -item[2], item[3]),
        )
    ]
