"""Portões de evidência do ask: recusam cedo quando a recuperação ou a ancoragem dos claims é fraca."""

from escolio.corpus.ask_retrieval import RetrievalStrategy
from escolio.retrieval.models import AnswerClaim, SearchHit
from escolio.retrieval.search import match_terms_in_text, terms_missing_from_vocabulary

# (motivo da recusa, limitações exibidas ao usuário)
Rejection = tuple[str, list[str]]


def vocabulary_rejection(query_terms: list[str], vocabulary_stems: frozenset[str] | None) -> Rejection | None:
    """Recusa quando um termo de conteúdo da pergunta não aparece em nenhuma nota do corpus.

    Um termo assim quase sempre é o assunto da pergunta ("senha", "Splunk", "orçamento"): os outros termos
    acham trechos parecidos e o chat responderia outra coisa. No benchmark, separa 6 de 10 negativas sem
    recusar nenhuma das 39 positivas.
    """
    missing_terms = terms_missing_from_vocabulary(query_terms, vocabulary_stems) if vocabulary_stems else []
    if not missing_terms:
        return None
    quoted = ', '.join(f'"{term}"' for term in missing_terms)
    verb = 'aparece' if len(missing_terms) == 1 else 'aparecem'
    return ('query_term_not_in_corpus', [f'A pergunta cita {quoted}, que não {verb} em nenhuma nota do corpus.'])


def retrieval_rejection(
    *,
    strategy: RetrievalStrategy,
    hits: list[SearchHit],
    min_term_coverage: float,
    min_vector_score: float,
    min_vector_term_coverage: float,
    min_hybrid_term_coverage: float,
) -> Rejection | None:
    """Recusa quando os hits recuperados não trazem evidência lexical ou score suficiente para a estratégia."""
    if not hits:
        return ('no_retrieval_hits', ['Nenhum trecho do corpus contém termos informativos suficientes da pergunta.'])

    top_hit = hits[0]
    if strategy == 'lexical' and top_hit.term_coverage < min_term_coverage:
        return (
            'insufficient_term_coverage',
            ['Os trechos recuperados compartilham poucos termos informativos com a pergunta.'],
        )
    if strategy == 'vector' and (top_hit.score < min_vector_score or top_hit.term_coverage < min_vector_term_coverage):
        return (
            'insufficient_vector_evidence',
            ['Os hits vetoriais recuperados não apresentam evidência lexical ou score suficiente.'],
        )
    if strategy == 'hybrid' and top_hit.term_coverage < min_hybrid_term_coverage and len(top_hit.matched_terms) < 1:
        return (
            'insufficient_hybrid_evidence',
            ['Os hits híbridos recuperados não apresentam evidência lexical suficiente.'],
        )
    return None


def grounding_rejection(
    *,
    query_terms: list[str],
    named_query_terms: list[str],
    strategy: RetrievalStrategy,
    claims: list[AnswerClaim],
    answer: str,
    min_vector_term_coverage: float,
) -> Rejection | None:
    """Recusa quando os claims extraídos não são citáveis, não ancoram a pergunta ou não trazem os nomes citados nela."""
    if not claims or any(not claim.citations for claim in claims):
        return (
            'citation_validation_failed',
            ['A evidência foi recuperada, mas não gerou frases extraídas citáveis de forma consistente.'],
        )

    grounded_text = ' '.join(claim.text for claim in claims)
    grounded_matches, grounded_coverage = match_terms_in_text(query_terms, grounded_text)
    if strategy in {'vector', 'hybrid'} and grounded_coverage < min_vector_term_coverage:
        if len(grounded_matches) <= 1:
            reason = 'insufficient_vector_specificity' if strategy == 'vector' else 'insufficient_hybrid_specificity'
            return (reason, ['As frases extraídas não trouxeram especificidade textual suficiente.'])
        return (
            'insufficient_grounded_claims',
            ['As frases extraídas não mantiveram ancoragem textual suficiente com a pergunta.'],
        )

    if strategy in {'vector', 'hybrid'} and named_query_terms:
        _, named_coverage = match_terms_in_text(named_query_terms, grounded_text)
        if named_coverage < 1.0:
            return ('missing_named_anchor', ['A resposta não sustentou os nomes citados na pergunta.'])

    if strategy in {'vector', 'hybrid'}:
        best_claim_match_count = max((len(match_terms_in_text(query_terms, claim.text)[0]) for claim in claims), default=0)
        if (
            len(query_terms) >= 3
            and best_claim_match_count <= 1
            and len(answer) < 80
            and all(claim.support_level == 'partial' for claim in claims)
        ):
            reason = 'insufficient_vector_specificity' if strategy == 'vector' else 'insufficient_hybrid_specificity'
            return (
                reason,
                ['A resposta recuperada ficou curta e pouco específica para os termos da pergunta.'],
            )
    return None
