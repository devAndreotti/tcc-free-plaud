from pathlib import Path

from escolio.app.config import Settings
from escolio.corpus.ask import (
    answer_corpus_with_citations,
    build_answer_contexts,
    validate_generated_answer,
)
from escolio.corpus.service import index_corpus_path
from escolio.notes.metadata import build_note_id
from escolio.notes.schemas import Note
from escolio.retrieval.models import AnswerClaim, Chunk, Citation, SearchHit
from escolio.retrieval.rag import (
    _clean_claim_candidate,
    _question_needs_multiple_claims,
)
from escolio.retrieval.search import (
    _stem_like,
    extract_named_query_terms,
    terms_missing_from_vocabulary,
)
from escolio.storage.sqlite import init_sqlite, list_chunks
from escolio.storage.vector import LocalVectorStore


class FakeEmbedder:
    model_name = 'fake-hash'

    def embed(self, texts: list[str]) -> list[list[float]]:
        embeddings: list[list[float]] = []
        for text in texts:
            vector = [0.0] * 16
            for token in text.lower().split():
                slot = sum(ord(char) for char in token) % len(vector)
                vector[slot] += 1.0
            embeddings.append(vector)
        return embeddings


class StubVectorStore:
    def __init__(self, hits: list[SearchHit]) -> None:
        self.hits = hits

    def query(self, query_embedding: list[float], *, top_k: int = 5, note_id: str | None = None) -> list[SearchHit]:
        return self.hits[:top_k]


class FakeAnswerProvider:
    provider_name = 'fake'
    model = 'fake-model'

    def __init__(self) -> None:
        self.calls: list[tuple[str, list[str]]] = []

    def answer(self, question: str, contexts: list[str]) -> str:
        self.calls.append((question, contexts))
        return 'RabbitMQ foi adotado como message broker padrao do pipeline.'


class UnsupportedNumberAnswerProvider:
    provider_name = 'unsupported-number'

    def answer(self, question: str, contexts: list[str]) -> str:
        return 'RabbitMQ foi adotado como message broker padrao do pipeline com lote de 64 KB.'


class SentinelAnswerProvider:
    provider_name = 'sentinel'

    def answer(self, question: str, contexts: list[str]) -> str:
        return 'NAO_ENCONTRADO: os dados recuperados nao sustentam resposta.'


class GenericNoAnswerProvider:
    provider_name = 'generic'

    def answer(self, question: str, contexts: list[str]) -> str:
        return 'Nao consegui recuperar essa informacao. Voce pode verificar a documentacao oficial.'


class FailingAnswerProvider:
    provider_name = 'failing'

    def answer(self, question: str, contexts: list[str]) -> str:
        raise RuntimeError('provider fora do ar')


class SecretLeakingAnswerProvider:
    provider_name = 'secret-leaking'

    def answer(self, question: str, contexts: list[str]) -> str:
        raise RuntimeError('HTTP 401: {"error":"bad key sk-secret"}')


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        workspace_dir=tmp_path,
        data_dir=tmp_path / 'data',
        notes_dir=tmp_path / 'data' / 'corpus' / 'notes',
        datasets_dir=tmp_path / 'data' / 'datasets',
        results_dir=tmp_path / 'data' / 'results',
        sqlite_path=tmp_path / 'data' / 'results' / 'escolio.sqlite3',
        vector_store_dir=tmp_path / 'data' / 'results' / 'vector_store',
        vector_collection_name='corpus_ask_test',
        embedding_model='fake-hash',
        default_chunk_size=220,
        default_chunk_overlap=40,
    )


def _chunk(chunk_id: str, note_id: str, text: str) -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        note_id=note_id,
        note_version=1,
        chunk_index=0,
        char_start=0,
        char_end=len(text),
        chunk_size=220,
        overlap=40,
        chunk_text=text,
        token_count=len(text.split()),
        strategy='fixed_window',
        normalized_text_sha256=f'{chunk_id}-normalized',
        text_sha256=f'{chunk_id}-text',
        pipeline_version='test',
    )


def _note(tmp_path: Path, note_id: str = 'note-1') -> Note:
    source_path = tmp_path / f'{note_id}.md'
    return Note(
        note_id=note_id,
        note_version=1,
        source_type='md',
        source_path=source_path,
        source_name=source_path.name,
        title='Nota de arquitetura',
        summary='Resumo.',
        topics=[],
        tasks=[],
        tags=['md'],
        raw_text='',
        normalized_text='',
        structured_markdown='',
        content_hash='a' * 64,
    )


def _build_distributed_corpus(root: Path) -> None:
    root.mkdir()
    (root / '01_contexto_base.md').write_text(
        '# Contexto base\n\n'
        'RabbitMQ foi adotado como message broker padrao do pipeline.\n',
        encoding='utf-8',
    )
    (root / '02_detalhe_operacional.md').write_text(
        '# Detalhe operacional\n\n'
        'O runbook de operacao do broker ficou sob responsabilidade da equipe de Plataforma. '
        'O prazo combinado para entregar a primeira versao operacional e de 15 dias corridos. '
        'Esse runbook deve cobrir filas e reprocessamento.\n',
        encoding='utf-8',
    )
    (root / '03_restricao_arquitetural.md').write_text(
        '# Restricao arquitetural\n\n'
        'O padrao Bronze, Silver e Gold divide o pipeline de dados.\n',
        encoding='utf-8',
    )


def _build_short_anchor_corpus(root: Path) -> None:
    root.mkdir()
    (root / 'estrutura-disco-c.md').write_text(
        '# Estrutura Disco C\n\n'
        'Estrutura Disco C descreve a organizacao do disco C para arquivos do sistema operacional.\n',
        encoding='utf-8',
    )
    (root / 'estrutura-disco-d.md').write_text(
        '# Estrutura Disco D\n\n'
        'Estrutura Disco D descreve a organizacao do disco D para arquivos de trabalho e repositorios.\n',
        encoding='utf-8',
    )


def test_build_answer_contexts_includes_clean_chunk_evidence_and_budget(tmp_path: Path) -> None:
    chunk = _chunk(
        'chunk-1',
        'note-1',
        '---\ntitle: metadata repetida\nstatus: draft\n---\n'
        '# Arquitetura\n\nRabbitMQ foi adotado como message broker padrao do pipeline. '
        'A equipe Plataforma ficou responsavel pelo runbook.',
    )
    hit = SearchHit(chunk=chunk, score=1.0, matched_terms=['rabbitmq'], term_coverage=1.0, strategy='lexical')
    citation = Citation(
        note_id='note-1',
        note_version=1,
        chunk_id='chunk-1',
        snippet='RabbitMQ foi adotado como message broker padrao do pipeline.',
        source_path=str(tmp_path / 'note-1.md'),
        char_start=0,
        char_end=len(chunk.chunk_text),
    )
    claim = AnswerClaim(
        text='RabbitMQ foi adotado como message broker padrao do pipeline.',
        citations=[citation],
        support_level='direct',
    )

    contexts = build_answer_contexts(
        [claim],
        [hit],
        {'note-1': _note(tmp_path)},
        max_total_chars=460,
        max_context_chars=420,
    )

    assert len(contexts) == 1
    context = contexts[0]
    assert 'source_path:' in context
    assert 'chunk_id: chunk-1' in context
    assert 'claim_extrativo: RabbitMQ foi adotado' in context
    assert 'trecho:' in context
    assert 'RabbitMQ foi adotado como message broker' in context
    assert 'metadata repetida' not in context
    assert len(context) <= 420
    assert sum(len(item) for item in contexts) <= 460


def test_validate_generated_answer_rejects_unsupported_numbers(tmp_path: Path) -> None:
    claim = AnswerClaim(
        text='RabbitMQ foi adotado como message broker padrao do pipeline.',
        citations=[
            Citation(
                note_id='note-1',
                note_version=1,
                chunk_id='chunk-1',
                snippet='RabbitMQ foi adotado como message broker padrao do pipeline.',
                source_path=str(tmp_path / 'note-1.md'),
                char_start=0,
                char_end=60,
            )
        ],
        support_level='direct',
    )

    validation = validate_generated_answer(
        'Qual message broker foi adotado?',
        'RabbitMQ foi adotado como message broker padrao do pipeline com lote de 64 KB.',
        ['RabbitMQ foi adotado como message broker padrao do pipeline.'],
        [claim],
    )

    assert validation.action == 'fallback_extractive'
    assert validation.reason == 'unsupported_number'


def test_validate_generated_answer_turns_sentinel_into_no_answer() -> None:
    validation = validate_generated_answer(
        'Qual message broker foi adotado?',
        'NAO_ENCONTRADO: os dados recuperados nao sustentam resposta.',
        ['RabbitMQ foi adotado como message broker padrao do pipeline.'],
        [],
    )

    assert validation.action == 'no_answer'
    assert validation.reason == 'generated_no_answer_sentinel'


def test_validate_generated_answer_accepts_faithful_short_answer(tmp_path: Path) -> None:
    claim = AnswerClaim(
        text='RabbitMQ foi adotado como message broker padrao do pipeline.',
        citations=[
            Citation(
                note_id='note-1',
                note_version=1,
                chunk_id='chunk-1',
                snippet='RabbitMQ foi adotado como message broker padrao do pipeline.',
                source_path=str(tmp_path / 'note-1.md'),
                char_start=0,
                char_end=60,
            )
        ],
        support_level='direct',
    )

    validation = validate_generated_answer(
        'Qual message broker foi adotado?',
        'RabbitMQ foi adotado como message broker padrao do pipeline.',
        ['RabbitMQ foi adotado como message broker padrao do pipeline.'],
        [claim],
    )

    assert validation.action == 'accept'
    assert validation.reason is None


def test_answer_corpus_with_citations_stitches_multiple_files(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    root = tmp_path / 'corpus'
    _build_distributed_corpus(root)
    embedder = FakeEmbedder()
    vector_store = LocalVectorStore(settings.vector_store_dir, collection_name=settings.vector_collection_name)
    connection = init_sqlite(settings.sqlite_path)
    index_corpus_path(root, settings=settings, connection=connection, vector_store=vector_store, embedder=embedder, recursive=True)

    response = answer_corpus_with_citations(
        'Qual message broker foi adotado, qual equipe ficou responsavel pelo runbook e qual padrao divide o pipeline em Bronze, Silver e Gold?',
        connection=connection,
        vector_store=vector_store,
        embedder=embedder,
        strategy='hybrid',
        top_k=6,
    )

    assert response.status == 'answer'
    assert response.answer
    assert 'RabbitMQ' in response.answer
    assert 'Plataforma' in response.answer
    assert 'Bronze, Silver e Gold' in response.answer
    assert '15 dias corridos' not in response.answer
    assert 'filas e reprocessamento' not in response.answer
    assert {source.doc_id for source in response.used_sources} >= {
        build_note_id(root / '01_contexto_base.md', root_path=root),
        build_note_id(root / '02_detalhe_operacional.md', root_path=root),
        build_note_id(root / '03_restricao_arquitetural.md', root_path=root),
    }
    assert len({citation.note_id for citation in response.citations}) >= 3


def test_answer_corpus_reranks_short_anchor_in_title_before_similar_document(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    root = tmp_path / 'corpus'
    _build_short_anchor_corpus(root)
    connection = init_sqlite(settings.sqlite_path)
    index_corpus_path(root, settings=settings, connection=connection, embedder=FakeEmbedder(), recursive=True)
    expected_note_id = build_note_id(root / 'estrutura-disco-d.md', root_path=root)

    response = answer_corpus_with_citations(
        'O que e Estrutura Disco D?',
        connection=connection,
        strategy='lexical',
        top_k=4,
        include_debug=True,
    )

    assert response.status == 'answer'
    assert response.debug is not None
    assert response.debug.hits
    assert response.debug.hits[0].note_id == expected_note_id
    assert 'Disco D' in (response.answer or '')


def test_answer_corpus_keeps_broad_question_answerable_without_short_anchor_boost(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    root = tmp_path / 'corpus'
    _build_short_anchor_corpus(root)
    connection = init_sqlite(settings.sqlite_path)
    index_corpus_path(root, settings=settings, connection=connection, embedder=FakeEmbedder(), recursive=True)

    response = answer_corpus_with_citations(
        'Como organizar estrutura de disco?',
        connection=connection,
        strategy='lexical',
        top_k=4,
    )

    assert response.status == 'answer'
    assert 'Disco' in (response.answer or '')


def test_answer_corpus_lexical_uses_fts_candidates(monkeypatch, tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    root = tmp_path / 'corpus'
    _build_distributed_corpus(root)
    connection = init_sqlite(settings.sqlite_path)
    index_corpus_path(root, settings=settings, connection=connection, embedder=FakeEmbedder(), recursive=True)
    calls = {'count': 0}

    from escolio.corpus import ask as ask_module

    original_search = ask_module.search_chunks_fts

    def spy_search_chunks_fts(*args, **kwargs):
        calls['count'] += 1
        return original_search(*args, **kwargs)

    monkeypatch.setattr(ask_module, 'search_chunks_fts', spy_search_chunks_fts)

    response = answer_corpus_with_citations(
        'Qual message broker foi adotado?',
        connection=connection,
        strategy='lexical',
        top_k=4,
    )

    assert calls['count'] >= 1
    assert response.status == 'answer'
    assert 'RabbitMQ' in (response.answer or '')


def test_answer_corpus_debug_is_disabled_by_default(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    root = tmp_path / 'corpus'
    _build_distributed_corpus(root)
    connection = init_sqlite(settings.sqlite_path)
    index_corpus_path(root, settings=settings, connection=connection, embedder=FakeEmbedder(), recursive=True)

    response = answer_corpus_with_citations(
        'Qual message broker foi adotado?',
        connection=connection,
        strategy='lexical',
        top_k=4,
    )

    assert response.status == 'answer'
    assert response.debug is None


def test_answer_corpus_debug_includes_hits_and_scores(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    root = tmp_path / 'corpus'
    _build_distributed_corpus(root)
    connection = init_sqlite(settings.sqlite_path)
    index_corpus_path(root, settings=settings, connection=connection, embedder=FakeEmbedder(), recursive=True)

    response = answer_corpus_with_citations(
        'Qual message broker foi adotado?',
        connection=connection,
        strategy='lexical',
        top_k=4,
        include_debug=True,
    )

    assert response.status == 'answer'
    assert response.debug is not None
    assert response.debug.strategy == 'lexical'
    assert response.debug.no_answer_reason is None
    assert response.debug.query_terms
    assert response.debug.hits
    assert response.debug.hits[0].chunk_id
    assert response.debug.hits[0].note_id
    assert response.debug.hits[0].score > 0
    assert response.debug.hits[0].strategy == 'lexical'
    assert 'message' in response.debug.hits[0].matched_terms
    assert response.debug.hits[0].source_path


def test_answer_corpus_debug_includes_stage_timings_without_provider(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    root = tmp_path / 'corpus'
    _build_distributed_corpus(root)
    connection = init_sqlite(settings.sqlite_path)
    index_corpus_path(root, settings=settings, connection=connection, embedder=FakeEmbedder(), recursive=True)

    response = answer_corpus_with_citations(
        'Qual message broker foi adotado?',
        connection=connection,
        strategy='lexical',
        top_k=4,
        include_debug=True,
    )

    assert response.debug is not None
    assert response.debug.timings is not None
    assert response.debug.timings.retrieval_ms >= 0
    assert response.debug.timings.claim_build_ms >= 0
    assert response.debug.timings.context_build_ms == 0
    assert response.debug.timings.provider_ms == 0
    assert response.debug.timings.validation_ms == 0
    assert response.debug.timings.total_ms >= response.debug.timings.retrieval_ms
    assert response.debug.answer_provider is None
    assert response.debug.provider_model is None


def test_answer_corpus_debug_includes_provider_timings_and_identity(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    root = tmp_path / 'corpus'
    _build_distributed_corpus(root)
    connection = init_sqlite(settings.sqlite_path)
    index_corpus_path(root, settings=settings, connection=connection, embedder=FakeEmbedder(), recursive=True)

    response = answer_corpus_with_citations(
        'Qual message broker foi adotado?',
        connection=connection,
        strategy='lexical',
        top_k=4,
        answer_provider=FakeAnswerProvider(),
        include_debug=True,
    )

    assert response.debug is not None
    assert response.debug.timings is not None
    assert response.debug.timings.context_build_ms >= 0
    assert response.debug.timings.provider_ms >= 0
    assert response.debug.timings.validation_ms >= 0
    assert response.debug.answer_provider == 'fake'
    assert response.debug.provider_model == 'fake-model'


def test_answer_corpus_abstains_when_question_term_is_not_in_any_note(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    root = tmp_path / 'corpus'
    _build_distributed_corpus(root)
    connection = init_sqlite(settings.sqlite_path)
    index_corpus_path(root, settings=settings, connection=connection, embedder=FakeEmbedder(), recursive=True)

    # "senha" não está em nota nenhuma; "broker" e "pipeline" achariam trechos parecidos.
    missing = answer_corpus_with_citations(
        'Qual a senha do broker do pipeline?', connection=connection, strategy='lexical', top_k=4
    )
    # "responsavel" é outra forma de "responsabilidade", que está no corpus.
    paraphrase = answer_corpus_with_citations(
        'Qual equipe ficou responsavel pelo runbook?', connection=connection, strategy='lexical', top_k=4
    )

    assert missing.reason_for_no_answer == 'query_term_not_in_corpus'
    assert missing.limitations == ['A pergunta cita "senha", que não aparece em nenhuma nota do corpus.']
    assert paraphrase.status == 'answer'
    assert 'Plataforma' in (paraphrase.answer or '')


def test_terms_missing_from_vocabulary_splits_identifiers_and_ignores_low_signal() -> None:
    vocabulary = frozenset(_stem_like(word) for word in ['note', 'id', 'redis', 'connect', 'timeout', 'arquivo'])

    assert terms_missing_from_vocabulary(['note_id', 'redis_connect_timeout', 'arquivo', 'foi'], vocabulary) == []
    assert terms_missing_from_vocabulary(['splunk', 'arquivo'], vocabulary) == ['splunk']


def test_named_query_terms_ignore_capitalized_question_word() -> None:
    assert extract_named_query_terms('Quantos registros a tabela eventos atingiu?') == []
    assert extract_named_query_terms('Quando o componente MAJOR muda?') == ['MAJOR']
    assert extract_named_query_terms('Qual versao do Kubernetes roda?') == ['Kubernetes']


def test_claim_cleaning_keeps_identifier_underscores_and_comparisons_ask_for_two_claims() -> None:
    assert _clean_claim_candidate('Ver `REDIS_CONNECT_TIMEOUT` no _arquivo_ certo.') == (
        'Ver REDIS_CONNECT_TIMEOUT no arquivo certo.'
    )
    assert _question_needs_multiple_claims('Qual a diferença entre CMD e ENTRYPOINT?')
    assert not _question_needs_multiple_claims('Qual message broker foi adotado?')


def test_answer_corpus_debug_no_answer_includes_reason_and_rejected_hits(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    root = tmp_path / 'corpus'
    _build_distributed_corpus(root)
    connection = init_sqlite(settings.sqlite_path)
    index_corpus_path(root, settings=settings, connection=connection, embedder=FakeEmbedder(), recursive=True)

    response = answer_corpus_with_citations(
        'Qual equipe usa o broker RabbitMQ?',
        connection=connection,
        strategy='lexical',
        top_k=4,
        min_term_coverage=0.99,
        include_debug=True,
    )

    assert response.status == 'no_answer'
    assert response.debug is not None
    assert response.debug.no_answer_reason == response.reason_for_no_answer
    assert response.debug.hits == []
    assert response.debug.rejected_hits


def test_answer_corpus_calls_answer_provider_only_after_citations(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    root = tmp_path / 'corpus'
    _build_distributed_corpus(root)
    connection = init_sqlite(settings.sqlite_path)
    index_corpus_path(root, settings=settings, connection=connection, embedder=FakeEmbedder(), recursive=True)
    provider = FakeAnswerProvider()

    response = answer_corpus_with_citations(
        'Qual message broker foi adotado?',
        connection=connection,
        strategy='lexical',
        top_k=4,
        answer_provider=provider,
    )

    assert response.status == 'answer'
    assert response.answer == 'RabbitMQ foi adotado como message broker padrao do pipeline.'
    assert response.citations
    assert len(provider.calls) == 1
    question, contexts = provider.calls[0]
    assert question == 'Qual message broker foi adotado?'
    assert any('RabbitMQ foi adotado' in context for context in contexts)
    assert any('source_path:' in context for context in contexts)
    assert any('chunk_id:' in context for context in contexts)


def test_answer_corpus_falls_back_when_generated_answer_has_unsupported_number(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    root = tmp_path / 'corpus'
    _build_distributed_corpus(root)
    connection = init_sqlite(settings.sqlite_path)
    index_corpus_path(root, settings=settings, connection=connection, embedder=FakeEmbedder(), recursive=True)

    response = answer_corpus_with_citations(
        'Qual message broker foi adotado?',
        connection=connection,
        strategy='lexical',
        top_k=4,
        answer_provider=UnsupportedNumberAnswerProvider(),
    )

    assert response.status == 'answer'
    assert '64 KB' not in (response.answer or '')
    assert 'RabbitMQ foi adotado' in (response.answer or '')
    assert any('unsupported_number' in limitation for limitation in response.limitations)


def test_answer_corpus_turns_generated_sentinel_into_no_answer(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    root = tmp_path / 'corpus'
    _build_distributed_corpus(root)
    connection = init_sqlite(settings.sqlite_path)
    index_corpus_path(root, settings=settings, connection=connection, embedder=FakeEmbedder(), recursive=True)

    response = answer_corpus_with_citations(
        'Qual message broker foi adotado?',
        connection=connection,
        strategy='lexical',
        top_k=4,
        answer_provider=SentinelAnswerProvider(),
    )

    assert response.status == 'no_answer'
    assert response.reason_for_no_answer == 'generated_no_answer_sentinel'


def test_answer_corpus_turns_generic_generated_no_answer_into_no_answer(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    root = tmp_path / 'corpus'
    _build_distributed_corpus(root)
    connection = init_sqlite(settings.sqlite_path)
    index_corpus_path(root, settings=settings, connection=connection, embedder=FakeEmbedder(), recursive=True)

    response = answer_corpus_with_citations(
        'Qual message broker foi adotado?',
        connection=connection,
        strategy='lexical',
        top_k=4,
        answer_provider=GenericNoAnswerProvider(),
    )

    assert response.status == 'no_answer'
    assert response.reason_for_no_answer == 'generated_generic_no_answer'


def test_answer_corpus_does_not_call_answer_provider_without_hits(tmp_path: Path) -> None:
    connection = init_sqlite(tmp_path / 'empty.sqlite3')
    provider = FakeAnswerProvider()

    response = answer_corpus_with_citations(
        'Qual message broker foi adotado?',
        connection=connection,
        strategy='lexical',
        top_k=4,
        answer_provider=provider,
    )

    assert response.status == 'no_answer'
    assert response.reason_for_no_answer == 'empty_corpus'
    assert provider.calls == []


def test_answer_corpus_falls_back_to_extractive_answer_when_provider_fails(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    root = tmp_path / 'corpus'
    _build_distributed_corpus(root)
    connection = init_sqlite(settings.sqlite_path)
    index_corpus_path(root, settings=settings, connection=connection, embedder=FakeEmbedder(), recursive=True)

    response = answer_corpus_with_citations(
        'Qual message broker foi adotado?',
        connection=connection,
        strategy='lexical',
        top_k=4,
        answer_provider=FailingAnswerProvider(),
    )

    assert response.status == 'answer'
    assert 'RabbitMQ' in (response.answer or '')
    assert any('provider de resposta falhou' in limitation.lower() for limitation in response.limitations)


def test_answer_corpus_sanitizes_provider_failure_message(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    root = tmp_path / 'corpus'
    _build_distributed_corpus(root)
    connection = init_sqlite(settings.sqlite_path)
    index_corpus_path(root, settings=settings, connection=connection, embedder=FakeEmbedder(), recursive=True)

    response = answer_corpus_with_citations(
        'Qual message broker foi adotado?',
        connection=connection,
        strategy='lexical',
        top_k=4,
        answer_provider=SecretLeakingAnswerProvider(),
    )
    serialized = ' '.join(response.limitations)

    assert response.status == 'answer'
    assert 'Provider de resposta falhou' in serialized
    assert 'RuntimeError' in serialized
    assert 'sk-secret' not in serialized
    assert 'bad key' not in serialized


def test_answer_corpus_with_citations_returns_no_answer_for_irrelevant_question(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    root = tmp_path / 'corpus'
    _build_distributed_corpus(root)
    embedder = FakeEmbedder()
    vector_store = LocalVectorStore(settings.vector_store_dir, collection_name=settings.vector_collection_name)
    connection = init_sqlite(settings.sqlite_path)
    index_corpus_path(root, settings=settings, connection=connection, vector_store=vector_store, embedder=embedder, recursive=True)

    response = answer_corpus_with_citations(
        'Quais tecnologias o candidato domina para desenvolver apps mobile?',
        connection=connection,
        vector_store=vector_store,
        embedder=embedder,
        strategy='hybrid',
        top_k=6,
    )

    assert response.status == 'no_answer'
    assert response.no_answer is True
    assert response.reason_for_no_answer is not None


def test_answer_corpus_filters_stale_vector_hits_before_citations(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    root = tmp_path / 'corpus'
    _build_distributed_corpus(root)
    connection = init_sqlite(settings.sqlite_path)
    index_corpus_path(root, settings=settings, connection=connection, embedder=FakeEmbedder(), recursive=True)
    stale = _chunk('stale-filas-1', 'stale-filas', 'O runbook deve cobrir as filas de um corpus antigo.')
    vector_store = StubVectorStore([SearchHit(chunk=stale, score=0.99, strategy='vector')])

    response = answer_corpus_with_citations(
        'Quais filas o runbook deve cobrir?',
        connection=connection,
        vector_store=vector_store,  # type: ignore[arg-type]
        embedder=FakeEmbedder(),
        strategy='vector',
        top_k=4,
    )

    assert response.status == 'no_answer'
    assert response.no_answer is True
    assert response.citations == []
    assert all(source.doc_id != 'stale-filas' for source in response.used_sources)
    assert any('stale' in limitation.lower() or 'obsoleto' in limitation.lower() for limitation in response.limitations)


def test_answer_corpus_uses_valid_vector_hit_after_dropping_stale_hit(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    root = tmp_path / 'corpus'
    _build_distributed_corpus(root)
    connection = init_sqlite(settings.sqlite_path)
    index_corpus_path(root, settings=settings, connection=connection, embedder=FakeEmbedder(), recursive=True)
    context_note_id = build_note_id(root / '01_contexto_base.md', root_path=root)
    valid_chunk = next(chunk for chunk in list_chunks(connection) if chunk.note_id == context_note_id)
    stale = _chunk('stale-broker-1', 'stale-broker', 'RabbitMQ foi adotado como message broker em outro corpus.')
    vector_store = StubVectorStore(
        [
            SearchHit(chunk=stale, score=0.99, strategy='vector'),
            SearchHit(chunk=valid_chunk, score=0.95, strategy='vector'),
        ]
    )

    response = answer_corpus_with_citations(
        'Qual message broker foi adotado?',
        connection=connection,
        vector_store=vector_store,  # type: ignore[arg-type]
        embedder=FakeEmbedder(),
        strategy='vector',
        top_k=4,
    )

    assert response.status == 'answer'
    assert 'RabbitMQ' in (response.answer or '')
    assert {citation.note_id for citation in response.citations} == {context_note_id}
    assert all(citation.note_id != 'stale-broker' for citation in response.citations)
