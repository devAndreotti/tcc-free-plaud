import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from free_plaud.cli import app
from free_plaud.app.config import Settings
from free_plaud.notes.schemas import Note
from free_plaud.retrieval.indexer import index_note_in_vector_store
from free_plaud.retrieval.indexer import index_note
from free_plaud.retrieval.rag import answer_with_citations
from free_plaud.retrieval.search import extract_named_query_terms, lexical_search_hits
from free_plaud.storage.vector import LocalVectorStore

runner = CliRunner()


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


def _build_note(**overrides: object) -> Note:
    payload: dict[str, object] = {
        'note_id': 'note-rag',
        'note_version': 1,
        'source_type': 'md',
        'source_path': Path('rag.md'),
        'source_name': 'rag.md',
        'title': 'Nota sobre benchmark e retrieval',
        'summary': 'Resumo da nota.',
        'topics': [],
        'tasks': [],
        'tags': ['md'],
        'raw_text': (
            'O benchmark mede recall, latencia e cobertura de citacoes. '
            'A recuperacao usa chunks com offsets reproduziveis. '
            'O SQLite persiste notas, chunks e logs de processamento.'
        ),
        'normalized_text': (
            'O benchmark mede recall, latencia e cobertura de citacoes. '
            'A recuperacao usa chunks com offsets reproduziveis. '
            'O SQLite persiste notas, chunks e logs de processamento.'
        ),
        'structured_markdown': (
            '# Nota sobre benchmark e retrieval\n\n'
            'O benchmark mede recall, latencia e cobertura de citacoes.\n\n'
            'A recuperacao usa chunks com offsets reproduziveis.\n\n'
            'O SQLite persiste notas, chunks e logs de processamento.\n'
        ),
        'content_hash': 'a' * 64,
    }
    payload.update(overrides)
    return Note(**payload)


def test_lexical_search_hits_expose_score_and_term_coverage() -> None:
    note = _build_note()
    chunks = index_note(note)

    hits = lexical_search_hits('O que o benchmark mede?', chunks, top_k=3)

    assert hits
    assert hits[0].score >= 2
    assert 0 < hits[0].term_coverage <= 1
    assert {'benchmark', 'mede'} <= set(hits[0].matched_terms)


def test_answer_with_citations_returns_structured_answer_with_claims_and_citations() -> None:
    note = _build_note()

    response = answer_with_citations(note, 'O que o benchmark mede?', top_k=3)

    assert response.status == 'answer'
    assert response.no_answer is False
    assert response.answer is not None
    assert 'benchmark' in response.answer.lower()
    assert response.claims
    assert response.citations
    assert response.claims[0].citations
    assert response.claims[0].citations[0].note_id == note.note_id
    assert response.claims[0].citations[0].chunk_id
    assert response.used_sources[0].doc_id == note.note_id
    assert response.reason_for_no_answer is None
    assert response.latency_ms >= 0


def test_answer_with_citations_returns_no_answer_when_there_is_no_evidence() -> None:
    note = _build_note()

    response = answer_with_citations(note, 'Como fazer OCR de imagens escaneadas?', top_k=3)

    assert response.status == 'no_answer'
    assert response.no_answer is True
    assert response.answer is None
    assert response.claims == []
    assert response.citations == []
    assert response.reason_for_no_answer == 'no_retrieval_hits'


def test_answer_with_citations_abstains_on_low_term_coverage_even_with_generic_match() -> None:
    note = _build_note(
        raw_text='O sistema opera localmente e persiste notas em SQLite.',
        normalized_text='O sistema opera localmente e persiste notas em SQLite.',
        structured_markdown='# Sistema local\n\nO sistema opera localmente e persiste notas em SQLite.\n',
        content_hash='b' * 64,
    )

    response = answer_with_citations(note, 'Como o sistema gera embeddings vetoriais?', top_k=3)

    assert response.status == 'no_answer'
    assert response.no_answer is True
    assert response.answer is None
    assert response.reason_for_no_answer == 'insufficient_term_coverage'
    assert response.used_sources


def test_answer_with_citations_does_not_treat_substring_matches_as_evidence() -> None:
    note = _build_note(
        raw_text='Existe um processo interno com revisoes periodicas.',
        normalized_text='Existe um processo interno com revisoes periodicas.',
        structured_markdown='# Processo interno\n\nExiste um processo interno com revisoes periodicas.\n',
        content_hash='c' * 64,
    )

    response = answer_with_citations(note, 'OCR juridico', top_k=3)

    assert response.status == 'no_answer'
    assert response.no_answer is True
    assert response.reason_for_no_answer == 'no_retrieval_hits'


def test_answer_with_citations_prefers_heading_plus_body_over_heading_only() -> None:
    note = _build_note(
        raw_text=(
            'OBJETIVO DA SESSAO\n\n'
            'Avaliar as propostas tecnicas para adocao de um message broker na plataforma.\n\n'
            'A equipe analisou riscos de operacao e rollout.'
        ),
        normalized_text=(
            'OBJETIVO DA SESSAO\n\n'
            'Avaliar as propostas tecnicas para adocao de um message broker na plataforma.\n\n'
            'A equipe analisou riscos de operacao e rollout.'
        ),
        structured_markdown=(
            '# Ata tecnica\n\n'
            'OBJETIVO DA SESSAO\n\n'
            'Avaliar as propostas tecnicas para adocao de um message broker na plataforma.\n\n'
            'A equipe analisou riscos de operacao e rollout.\n'
        ),
        content_hash='e' * 64,
    )

    response = answer_with_citations(note, 'Qual era o objetivo da sessao?', top_k=3)

    assert response.status == 'answer'
    assert response.answer is not None
    assert 'avaliar as propostas tecnicas' in response.answer.lower()


def test_answer_with_citations_uses_following_sentence_for_qa_style_chunks() -> None:
    note = _build_note(
        raw_text=(
            'Qual foi um projeto que te desafiou?\n\n'
            'No semestre passado, trabalhei em um detector de exercicios usando MediaPipe e Flask.\n'
        ),
        normalized_text=(
            'Qual foi um projeto que te desafiou?\n\n'
            'No semestre passado, trabalhei em um detector de exercicios usando MediaPipe e Flask.\n'
        ),
        structured_markdown=(
            '# Preparacao de entrevista\n\n'
            'Qual foi um projeto que te desafiou?\n\n'
            'No semestre passado, trabalhei em um detector de exercicios usando MediaPipe e Flask.\n'
        ),
        content_hash='1' * 64,
    )

    response = answer_with_citations(note, 'Qual projeto te desafiou?', top_k=3)

    assert response.status == 'answer'
    assert response.answer is not None
    assert 'detector de exercicios' in response.answer.lower()


def test_answer_with_citations_prefers_specific_list_items_over_generic_rollout_sentence() -> None:
    note = _build_note(
        raw_text=(
            'DISCUSSAO TECNICA\n\n'
            'A terceira condicionante e que a adocao comeca com dois topicos de baixo risco — '
            'notificacoes de email e logs de auditoria — antes de migrar os eventos criticos.\n\n'
            'DECISOES TOMADAS\n\n'
            '3. Iniciar rollout em Q2/2025, comecando pelos topicos de menor risco.\n'
        ),
        normalized_text=(
            'DISCUSSAO TECNICA\n\n'
            'A terceira condicionante e que a adocao comeca com dois topicos de baixo risco — '
            'notificacoes de email e logs de auditoria — antes de migrar os eventos criticos.\n\n'
            'DECISOES TOMADAS\n\n'
            '3. Iniciar rollout em Q2/2025, comecando pelos topicos de menor risco.\n'
        ),
        structured_markdown=(
            '# Ata tecnica\n\n'
            'DISCUSSAO TECNICA\n\n'
            'A terceira condicionante e que a adocao comeca com dois topicos de baixo risco — '
            'notificacoes de email e logs de auditoria — antes de migrar os eventos criticos.\n\n'
            'DECISOES TOMADAS\n\n'
            '3. Iniciar rollout em Q2/2025, comecando pelos topicos de menor risco.\n'
        ),
        content_hash='2' * 64,
    )

    response = answer_with_citations(note, 'Quais topicos de baixo risco iniciariam o rollout?', top_k=3)

    assert response.status == 'answer'
    assert response.answer is not None
    assert 'notificacoes de email' in response.answer.lower()
    assert 'logs de auditoria' in response.answer.lower()


def test_answer_with_citations_prefers_exact_embedding_model_over_generic_embedding_sentence() -> None:
    note = _build_note(
        raw_text=(
            '### 2.5 Semantico\n\n'
            'O chunking semantico utiliza embeddings de sentenca para identificar pontos de quebra.\n\n'
            '### 3.3 Infraestrutura\n\n'
            'Todos os experimentos foram executados sem GPU dedicada. '
            'O indice vetorial foi implementado com ChromaDB e os embeddings gerados com `nomic-embed-text-v1.5`.\n'
        ),
        normalized_text=(
            '### 2.5 Semantico\n\n'
            'O chunking semantico utiliza embeddings de sentenca para identificar pontos de quebra.\n\n'
            '### 3.3 Infraestrutura\n\n'
            'Todos os experimentos foram executados sem GPU dedicada. '
            'O indice vetorial foi implementado com ChromaDB e os embeddings gerados com `nomic-embed-text-v1.5`.\n'
        ),
        structured_markdown=(
            '# Artigo tecnico\n\n'
            '### 2.5 Semantico\n\n'
            'O chunking semantico utiliza embeddings de sentenca para identificar pontos de quebra.\n\n'
            '### 3.3 Infraestrutura\n\n'
            'Todos os experimentos foram executados sem GPU dedicada. '
            'O indice vetorial foi implementado com ChromaDB e os embeddings gerados com `nomic-embed-text-v1.5`.\n'
        ),
        content_hash='3' * 64,
    )

    response = answer_with_citations(note, 'Qual modelo de embedding foi usado nos experimentos?', top_k=3)

    assert response.status == 'answer'
    assert response.answer is not None
    assert 'nomic-embed-text-v1.5' in response.answer.lower()


def test_answer_with_citations_prefers_semantic_strategy_for_unstructured_documents() -> None:
    note = _build_note(
        raw_text=(
            '## 5. Discussao\n\n'
            'A estrategia hierarquica e a recomendacao padrao para documentos com estrutura explicita de headings.\n\n'
            'Para documentos sem estrutura formal - como e-mails, notas pessoais e transcricoes - '
            'o chunking semantico oferece ganhos mais expressivos.\n'
        ),
        normalized_text=(
            '## 5. Discussao\n\n'
            'A estrategia hierarquica e a recomendacao padrao para documentos com estrutura explicita de headings.\n\n'
            'Para documentos sem estrutura formal - como e-mails, notas pessoais e transcricoes - '
            'o chunking semantico oferece ganhos mais expressivos.\n'
        ),
        structured_markdown=(
            '# Artigo tecnico\n\n'
            '## 5. Discussao\n\n'
            'A estrategia hierarquica e a recomendacao padrao para documentos com estrutura explicita de headings.\n\n'
            'Para documentos sem estrutura formal - como e-mails, notas pessoais e transcricoes - '
            'o chunking semantico oferece ganhos mais expressivos.\n'
        ),
        content_hash='4' * 64,
    )

    response = answer_with_citations(
        note,
        'Qual estrategia e recomendada para documentos sem estrutura formal?',
        top_k=3,
    )

    assert response.status == 'answer'
    assert response.answer is not None
    assert 'chunking semantico' in response.answer.lower()
    assert 'sem estrutura formal' in response.answer.lower()


def test_answer_with_citations_merges_adjacent_bullets_for_multi_part_question() -> None:
    note = _build_note(
        raw_text=(
            'ANEXO I - ESPECIFICACOES TECNICAS\n\n'
            '- Portal do colaborador (React + Node.js)\n'
            '- Modulo financeiro (Python + PostgreSQL)\n'
            '- Integracao com ERP legado (API REST)\n'
        ),
        normalized_text=(
            'ANEXO I - ESPECIFICACOES TECNICAS\n\n'
            '- Portal do colaborador (React + Node.js)\n'
            '- Modulo financeiro (Python + PostgreSQL)\n'
            '- Integracao com ERP legado (API REST)\n'
        ),
        structured_markdown=(
            '# Contrato tecnico\n\n'
            'ANEXO I - ESPECIFICACOES TECNICAS\n\n'
            '- Portal do colaborador (React + Node.js)\n'
            '- Modulo financeiro (Python + PostgreSQL)\n'
            '- Integracao com ERP legado (API REST)\n'
        ),
        content_hash='5' * 64,
    )

    response = answer_with_citations(
        note,
        'Quais tecnologias aparecem no Portal do colaborador e no modulo financeiro?',
        top_k=3,
    )

    assert response.status == 'answer'
    assert response.answer is not None
    assert 'react + node.js' in response.answer.lower()
    assert 'python + postgresql' in response.answer.lower()


def test_answer_with_citations_supports_vector_strategy(tmp_path: Path) -> None:
    note = _build_note(
        source_path=tmp_path / 'vector.md',
        source_name='vector.md',
    )
    vector_store = LocalVectorStore(tmp_path / 'vector_store', collection_name='vector_answer')

    response = answer_with_citations(
        note,
        'O que o benchmark mede?',
        top_k=3,
        strategy='vector',
        vector_store=vector_store,
        embedder=FakeEmbedder(),
    )

    assert response.status == 'answer'
    assert response.no_answer is False
    assert response.answer is not None
    assert response.citations
    assert response.claims
    assert response.used_sources


def test_answer_with_citations_supports_hybrid_strategy(tmp_path: Path) -> None:
    note = _build_note(
        source_path=tmp_path / 'hybrid.md',
        source_name='hybrid.md',
    )
    vector_store = LocalVectorStore(tmp_path / 'vector_store', collection_name='hybrid_answer')

    response = answer_with_citations(
        note,
        'O que o benchmark mede?',
        top_k=3,
        strategy='hybrid',
        vector_store=vector_store,
        embedder=FakeEmbedder(),
    )

    assert response.status == 'answer'
    assert response.no_answer is False
    assert response.answer is not None
    assert response.citations
    assert response.claims
    assert response.used_sources


def test_answer_with_citations_vector_strategy_abstains_when_vector_evidence_is_weak(tmp_path: Path) -> None:
    note = _build_note(
        source_path=tmp_path / 'vector.md',
        source_name='vector.md',
    )
    vector_store = LocalVectorStore(tmp_path / 'vector_store', collection_name='vector_no_answer')

    response = answer_with_citations(
        note,
        'Como organizar notas pessoais no Obsidian?',
        top_k=3,
        strategy='vector',
        vector_store=vector_store,
        embedder=FakeEmbedder(),
    )

    assert response.status == 'no_answer'
    assert response.no_answer is True
    assert response.reason_for_no_answer == 'insufficient_vector_evidence'


def test_answer_with_citations_hybrid_strategy_abstains_when_hybrid_evidence_is_weak(tmp_path: Path) -> None:
    note = _build_note(
        source_path=tmp_path / 'hybrid.md',
        source_name='hybrid.md',
    )
    vector_store = LocalVectorStore(tmp_path / 'vector_store', collection_name='hybrid_no_answer')

    response = answer_with_citations(
        note,
        'Como organizar notas pessoais no Obsidian?',
        top_k=3,
        strategy='hybrid',
        vector_store=vector_store,
        embedder=FakeEmbedder(),
    )

    assert response.status == 'no_answer'
    assert response.no_answer is True
    assert response.reason_for_no_answer == 'missing_named_anchor'


def test_answer_with_citations_vector_strategy_abstains_when_named_anchor_is_missing(tmp_path: Path) -> None:
    note = _build_note(
        source_path=tmp_path / 'vector.md',
        source_name='vector.md',
        raw_text=(
            'O sistema organiza notas pessoais em lotes locais. '
            'As notas pessoais podem ser reestruturadas em Markdown para revisao posterior.'
        ),
        normalized_text=(
            'O sistema organiza notas pessoais em lotes locais. '
            'As notas pessoais podem ser reestruturadas em Markdown para revisao posterior.'
        ),
        structured_markdown=(
            '# Organizacao local\n\n'
            'O sistema organiza notas pessoais em lotes locais.\n\n'
            'As notas pessoais podem ser reestruturadas em Markdown para revisao posterior.\n'
        ),
        content_hash='d' * 64,
    )
    vector_store = LocalVectorStore(tmp_path / 'vector_store', collection_name='vector_named_anchor')

    response = answer_with_citations(
        note,
        'Como organizar notas pessoais no Obsidian?',
        top_k=3,
        strategy='vector',
        vector_store=vector_store,
        embedder=FakeEmbedder(),
    )

    assert response.status == 'no_answer'
    assert response.no_answer is True
    assert response.reason_for_no_answer == 'missing_named_anchor'


def test_answer_with_citations_vector_strategy_abstains_on_short_partial_single_term_answer(tmp_path: Path) -> None:
    note = _build_note(
        source_path=tmp_path / 'vector.md',
        source_name='vector.md',
        raw_text='Convocador: Diretoria de Tecnologia. Sala: Meet interno.',
        normalized_text='Convocador: Diretoria de Tecnologia. Sala: Meet interno.',
        structured_markdown='# Ata curta\n\nConvocador: Diretoria de Tecnologia.\n\nSala: Meet interno.\n',
        content_hash='f' * 64,
    )
    vector_store = LocalVectorStore(tmp_path / 'vector_store', collection_name='vector_specificity')

    response = answer_with_citations(
        note,
        'Quais tecnologias o candidato domina?',
        top_k=3,
        strategy='vector',
        vector_store=vector_store,
        embedder=FakeEmbedder(),
    )

    assert response.status == 'no_answer'
    assert response.no_answer is True
    assert response.reason_for_no_answer == 'insufficient_vector_specificity'


def test_answer_with_citations_rejects_unknown_strategy() -> None:
    note = _build_note()

    with pytest.raises(ValueError, match='strategy'):
        answer_with_citations(note, 'O que o benchmark mede?', strategy='reciprocal')  # type: ignore[arg-type]


def test_extract_named_query_terms_ignores_interrogatives_and_keeps_product_names() -> None:
    assert extract_named_query_terms('Como organizar notas pessoais no Obsidian?') == ['Obsidian']


def test_retrieval_ask_cli_renders_structured_json_response(tmp_path: Path) -> None:
    sample_file = tmp_path / 'ask.md'
    sample_file.write_text(
        '# Nota de teste\n\n'
        'O benchmark mede recall e latencia para comparar estrategias de recuperacao.\n',
        encoding='utf-8',
    )

    result = runner.invoke(
        app,
        [
            'retrieval',
            'ask',
            str(sample_file),
            '--question',
            'O que o benchmark mede?',
            '--top-k',
            '3',
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload['status'] == 'answer'
    assert payload['no_answer'] is False
    assert payload['citations']


def test_retrieval_ask_cli_keeps_json_parseable_with_unicode_source_paths(tmp_path: Path) -> None:
    sample_file = tmp_path / '📚 nota unicode.md'
    sample_file.write_text(
        '# Nota unicode\n\n'
        'O benchmark mede recall e latencia para comparar estrategias de recuperacao.\n',
        encoding='utf-8',
    )

    result = runner.invoke(
        app,
        [
            'retrieval',
            'ask',
            str(sample_file),
            '--question',
            'O que o benchmark mede?',
            '--top-k',
            '3',
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload['status'] == 'answer'
    assert payload['citations'][0]['source_path']


def test_retrieval_ask_cli_supports_vector_strategy(monkeypatch, tmp_path: Path) -> None:
    settings = Settings(
        workspace_dir=tmp_path,
        data_dir=tmp_path / 'data',
        notes_dir=tmp_path / 'data' / 'corpus' / 'notes',
        datasets_dir=tmp_path / 'data' / 'datasets',
        results_dir=tmp_path / 'data' / 'results',
        sqlite_path=tmp_path / 'data' / 'results' / 'free_plaud.sqlite3',
        vector_store_dir=tmp_path / 'data' / 'results' / 'vector_store',
        vector_collection_name='ask_vector',
        embedding_model='fake-hash',
    )
    sample_file = tmp_path / 'ask-vector.md'
    sample_file.write_text(
        '# Nota vetorial\n\n'
        'O benchmark mede recall e latencia para comparar estrategias de recuperacao.\n',
        encoding='utf-8',
    )

    monkeypatch.setattr('free_plaud.retrieval.cli.get_settings', lambda: settings)
    monkeypatch.setattr('free_plaud.retrieval.cli.get_embedder', lambda model_name: FakeEmbedder())

    result = runner.invoke(
        app,
        [
            'retrieval',
            'ask',
            str(sample_file),
            '--question',
            'O que o benchmark mede?',
            '--top-k',
            '3',
            '--strategy',
            'vector',
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload['status'] == 'answer'
    assert payload['no_answer'] is False
    assert payload['citations']


def test_retrieval_ask_cli_supports_hybrid_strategy(monkeypatch, tmp_path: Path) -> None:
    settings = Settings(
        workspace_dir=tmp_path,
        data_dir=tmp_path / 'data',
        notes_dir=tmp_path / 'data' / 'corpus' / 'notes',
        datasets_dir=tmp_path / 'data' / 'datasets',
        results_dir=tmp_path / 'data' / 'results',
        sqlite_path=tmp_path / 'data' / 'results' / 'free_plaud.sqlite3',
        vector_store_dir=tmp_path / 'data' / 'results' / 'vector_store',
        vector_collection_name='ask_hybrid',
        embedding_model='fake-hash',
    )
    sample_file = tmp_path / 'ask-hybrid.md'
    sample_file.write_text(
        '# Nota híbrida\n\n'
        'O benchmark mede recall e latencia para comparar estrategias de recuperacao.\n',
        encoding='utf-8',
    )

    monkeypatch.setattr('free_plaud.retrieval.cli.get_settings', lambda: settings)
    monkeypatch.setattr('free_plaud.retrieval.cli.get_embedder', lambda model_name: FakeEmbedder())

    result = runner.invoke(
        app,
        [
            'retrieval',
            'ask',
            str(sample_file),
            '--question',
            'O que o benchmark mede?',
            '--top-k',
            '3',
            '--strategy',
            'hybrid',
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload['status'] == 'answer'
    assert payload['no_answer'] is False
    assert payload['citations']


def test_retrieval_ask_cli_rejects_unknown_strategy(tmp_path: Path) -> None:
    sample_file = tmp_path / 'ask-invalid.md'
    sample_file.write_text(
        '# Nota de teste\n\n'
        'O benchmark mede recall e latencia para comparar estrategias de recuperacao.\n',
        encoding='utf-8',
    )

    result = runner.invoke(
        app,
        [
            'retrieval',
            'ask',
            str(sample_file),
            '--question',
            'O que o benchmark mede?',
            '--strategy',
            'rrf',
        ],
    )

    assert result.exit_code != 0
    assert 'strategy' in result.output
