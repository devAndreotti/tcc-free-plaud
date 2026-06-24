import dataclasses
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from free_plaud.cli import app
from free_plaud.app.config import Settings
from free_plaud.notes.schemas import Note
from free_plaud.retrieval.indexer import index_note
from free_plaud.retrieval.rag import SCORING, ClaimScoringConfig
from free_plaud.retrieval.rag import _rank_claim_candidates
from free_plaud.retrieval.rag import _claim_variant_score
from free_plaud.retrieval.rag import _trim_dangling_tail
from free_plaud.retrieval.rag import answer_with_citations
from free_plaud.retrieval.search import extract_named_query_terms, lexical_search_hits, normalize_query_terms
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


def test_claim_scoring_config_locks_calibrated_defaults() -> None:
    # Os pesos são calibrados; este teste força que qualquer alteração seja intencional.
    assert SCORING == ClaimScoringConfig()
    assert SCORING.noisy_min_length == 24
    assert SCORING.snippet_max_length == 220
    assert SCORING.question_like_max_length == 80
    assert SCORING.short_answer_max_length == 80
    assert (SCORING.rank_preferred_min, SCORING.rank_preferred_max) == (40, 260)
    assert SCORING.term_density_scale == 1000
    assert SCORING.dedupe_max_overlap == 0.65
    assert (SCORING.support_direct_coverage, SCORING.support_direct_score) == (0.6, 0.7)
    assert SCORING.coverage_drop_tolerance == 33
    assert SCORING.length_gain_margin == 20
    assert SCORING.dangling_comma_max_distance == 48


def test_claim_scoring_config_is_frozen() -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        SCORING.noisy_min_length = 1  # type: ignore[misc]


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
    assert 'a primeira condicionante' not in response.answer.lower()
    assert 'a segunda condicionante' not in response.answer.lower()


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
    assert 'cpuintel xeon' not in response.answer.lower()
    assert '128 gbram' not in response.answer.lower()
    assert 'corpus foi composto por 800 documentos' not in response.answer.lower()


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
    assert 'melhor trade-off geral' not in response.answer.lower()
    assert 'recomendacao padrao para documentos com estrutura explicita' not in response.answer.lower()


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
    assert 'anexo i - especificacoes tecnicas' not in response.answer.lower()
    assert 'os servicos abrangem os seguintes sistemas e modulos' not in response.answer.lower()


def test_answer_with_citations_keeps_stable_short_answer_for_message_broker_decision() -> None:
    note = _build_note(
        raw_text=(
            'DECISOES TOMADAS\n\n'
            '1. Adotar Apache Kafka como message broker padrao da plataforma.\n'
            '2. Registrar a decisao em ADR-2025-07 com status Aceito.\n'
        ),
        normalized_text=(
            'DECISOES TOMADAS\n\n'
            '1. Adotar Apache Kafka como message broker padrao da plataforma.\n'
            '2. Registrar a decisao em ADR-2025-07 com status Aceito.\n'
        ),
        structured_markdown=(
            '# Ata tecnica\n\n'
            'DECISOES TOMADAS\n\n'
            '1. Adotar Apache Kafka como message broker padrao da plataforma.\n'
            '2. Registrar a decisao em ADR-2025-07 com status Aceito.\n'
        ),
        content_hash='6' * 64,
    )

    response = answer_with_citations(note, 'Qual message broker foi adotado como padrao da plataforma?', top_k=3)

    assert response.status == 'answer'
    assert response.answer is not None
    assert 'apache kafka' in response.answer.lower()
    assert 'message broker padrao da plataforma' in response.answer.lower()


def test_answer_with_citations_keeps_qualifier_for_confidentiality_deadline() -> None:
    note = _build_note(
        raw_text=(
            'CLAUSULA 4 - CONFIDENCIALIDADE\n\n'
            'As partes obrigam-se a manter sigilo sobre informacoes tecnicas, comerciais e estrategicas '
            'as quais tiverem acesso em razao deste contrato, pelo prazo de 3 (tres) anos apos o encerramento '
            'da vigencia. A obrigacao de confidencialidade nao se aplica a informacoes publicas.\n'
        ),
        normalized_text=(
            'CLAUSULA 4 - CONFIDENCIALIDADE\n\n'
            'As partes obrigam-se a manter sigilo sobre informacoes tecnicas, comerciais e estrategicas '
            'as quais tiverem acesso em razao deste contrato, pelo prazo de 3 (tres) anos apos o encerramento '
            'da vigencia. A obrigacao de confidencialidade nao se aplica a informacoes publicas.\n'
        ),
        structured_markdown=(
            '# Contrato\n\n'
            'CLAUSULA 4 - CONFIDENCIALIDADE\n\n'
            'As partes obrigam-se a manter sigilo sobre informacoes tecnicas, comerciais e estrategicas '
            'as quais tiverem acesso em razao deste contrato, pelo prazo de 3 (tres) anos apos o encerramento '
            'da vigencia. A obrigacao de confidencialidade nao se aplica a informacoes publicas.\n'
        ),
        content_hash='7' * 64,
    )

    response = answer_with_citations(
        note,
        'Qual e o prazo de confidencialidade apos o encerramento da vigencia?',
        top_k=3,
    )

    assert response.status == 'answer'
    assert response.answer is not None
    assert '3 (tres) anos' in response.answer.lower()
    assert (
        'obrigacao de confidencialidade' in response.answer.lower()
        or 'sigilo' in response.answer.lower()
    )


def test_answer_with_citations_keeps_monetary_amount_with_decimal_cents() -> None:
    note = _build_note(
        raw_text=(
            'PARTES: EMPRESA CONTRATANTE e FORNECEDORA LTDA\n'
            'Vigencia: 01/04/2025 a 31/03/2026\n'
            'Valor total: R$ 144.000,00 (cento e quarenta e quatro mil reais).\n'
        ),
        normalized_text=(
            'PARTES: EMPRESA CONTRATANTE e FORNECEDORA LTDA\n'
            'Vigencia: 01/04/2025 a 31/03/2026\n'
            'Valor total: R$ 144.000,00 (cento e quarenta e quatro mil reais).\n'
        ),
        structured_markdown=(
            '# Contrato\n\n'
            'PARTES: EMPRESA CONTRATANTE e FORNECEDORA LTDA\n'
            'Vigencia: 01/04/2025 a 31/03/2026\n'
            'Valor total: R$ 144.000,00 (cento e quarenta e quatro mil reais).\n'
        ),
        content_hash='a7' * 32,
    )

    response = answer_with_citations(note, 'Qual e o valor total do contrato?', top_k=3)

    assert response.status == 'answer'
    assert response.answer is not None
    assert 'r$ 144.000,00' in response.answer.lower()


def test_answer_with_citations_keeps_confidentiality_subject_when_trimming_clause() -> None:
    note = _build_note(
        raw_text=(
            'CLAUSULA 4 - CONFIDENCIALIDADE\n\n'
            'As partes obrigam-se a manter sigilo sobre informacoes tecnicas, comerciais e estrategicas '
            'as quais tiverem acesso em razao deste contrato, pelo prazo de 3 (tres) anos apos o encerramento '
            'da vigencia, independentemente do motivo do encerramento.\n'
        ),
        normalized_text=(
            'CLAUSULA 4 - CONFIDENCIALIDADE\n\n'
            'As partes obrigam-se a manter sigilo sobre informacoes tecnicas, comerciais e estrategicas '
            'as quais tiverem acesso em razao deste contrato, pelo prazo de 3 (tres) anos apos o encerramento '
            'da vigencia, independentemente do motivo do encerramento.\n'
        ),
        structured_markdown=(
            '# Contrato\n\n'
            'CLAUSULA 4 - CONFIDENCIALIDADE\n\n'
            'As partes obrigam-se a manter sigilo sobre informacoes tecnicas, comerciais e estrategicas '
            'as quais tiverem acesso em razao deste contrato, pelo prazo de 3 (tres) anos apos o encerramento '
            'da vigencia, independentemente do motivo do encerramento.\n'
        ),
        content_hash='b7' * 32,
    )

    response = answer_with_citations(
        note,
        'Qual e o prazo de confidencialidade apos o encerramento da vigencia?',
        top_k=3,
    )

    assert response.status == 'answer'
    assert response.answer is not None
    assert '3 (tres) anos' in response.answer.lower()
    assert response.answer.lower().startswith('as partes obrigam-se')


def test_trim_dangling_tail_preserves_currency_decimal_groups() -> None:
    candidate = 'Valor total: R$ 144.000,00 (cento e quarenta e quatro mil reais)'

    trimmed = _trim_dangling_tail(candidate)

    assert trimmed == candidate


def test_claim_variant_score_penalizes_low_information_legal_fragments() -> None:
    question = 'Qual e o prazo de confidencialidade apos o encerramento da vigencia?'
    query_terms = normalize_query_terms(question)
    full = (
        'As partes obrigam-se a manter sigilo sobre informacoes tecnicas, comerciais e estrategicas '
        'as quais tiverem acesso em razao deste contrato, pelo prazo de 3 (tres) anos apos o '
        'encerramento da vigencia, independentemente do motivo do encerramento.'
    )
    fragment = 'de 3 (tres) anos apos o encerramento da vigencia'

    full_score = _claim_variant_score(question, query_terms, full)
    fragment_score = _claim_variant_score(question, query_terms, fragment)

    assert full_score is not None
    assert fragment_score is not None
    assert full_score > fragment_score


def test_rank_claim_candidates_prefers_complete_legal_clause_over_time_fragment() -> None:
    question = 'Qual e o prazo de confidencialidade apos o encerramento da vigencia?'
    query_terms = normalize_query_terms(question)
    chunk_text = (
        'As partes comprometem-se a manter sigilo sobre todas as informacoes tecnicas, '
        'comerciais e estrategicas as quais tiverem acesso em razao deste contrato, pelo prazo '
        'de 3 (tres) anos apos o encerramento da vigencia, independentemente do motivo do\n\n'
        'encerramento. A obrigacao de confidencialidade nao se aplica a informacoes que sejam\n'
        'de dominio publico, que devam ser divulgadas por determinacao legal ou judicial.\n'
    )

    ranked = _rank_claim_candidates(chunk_text, question, query_terms)

    assert ranked
    top_candidate = ranked[0][1].lower()
    assert '3 (tres) anos' in top_candidate
    assert 'confidencialidade' in top_candidate or 'sigilo' in top_candidate
    assert not top_candidate.startswith('de 3 (tres) anos')


def test_answer_with_citations_keeps_priority_context_for_sla() -> None:
    note = _build_note(
        raw_text=(
            'ANEXO II - MATRIZ DE PRIORIDADES\n\n'
            'Prioridade Critica: sistema fora do ar ou perda de dados em producao. SLA: 2h.\n'
            'Prioridade Normal: incidentes sem impacto critico. SLA: 8h.\n'
        ),
        normalized_text=(
            'ANEXO II - MATRIZ DE PRIORIDADES\n\n'
            'Prioridade Critica: sistema fora do ar ou perda de dados em producao. SLA: 2h.\n'
            'Prioridade Normal: incidentes sem impacto critico. SLA: 8h.\n'
        ),
        structured_markdown=(
            '# Contrato\n\n'
            'ANEXO II - MATRIZ DE PRIORIDADES\n\n'
            'Prioridade Critica: sistema fora do ar ou perda de dados em producao. SLA: 2h.\n'
            'Prioridade Normal: incidentes sem impacto critico. SLA: 8h.\n'
        ),
        content_hash='8' * 64,
    )

    response = answer_with_citations(note, 'Qual e o SLA para prioridade critica?', top_k=3)

    assert response.status == 'answer'
    assert response.answer is not None
    assert 'prioridade critica' in response.answer.lower()
    assert 'sla: 2h' in response.answer.lower()


def test_answer_with_citations_keeps_historical_qualifier_for_scd_type_2() -> None:
    note = _build_note(
        raw_text=(
            'SCD Tipo 2 (Adicionar linha): Uma nova linha e inserida para o cliente com o novo endereco, '
            'e a linha anterior e marcada como inativa. Preserva o historico completo, mas aumenta o volume da dimensao.\n'
            'SCD Tipo 3 (Adicionar coluna): Preserva apenas a penultima versao.\n'
        ),
        normalized_text=(
            'SCD Tipo 2 (Adicionar linha): Uma nova linha e inserida para o cliente com o novo endereco, '
            'e a linha anterior e marcada como inativa. Preserva o historico completo, mas aumenta o volume da dimensao.\n'
            'SCD Tipo 3 (Adicionar coluna): Preserva apenas a penultima versao.\n'
        ),
        structured_markdown=(
            '# Modelagem\n\n'
            'SCD Tipo 2 (Adicionar linha): Uma nova linha e inserida para o cliente com o novo endereco, '
            'e a linha anterior e marcada como inativa. Preserva o historico completo, mas aumenta o volume da dimensao.\n'
            'SCD Tipo 3 (Adicionar coluna): Preserva apenas a penultima versao.\n'
        ),
        content_hash='9' * 64,
    )

    response = answer_with_citations(
        note,
        'Qual tipo de SCD preserva o historico completo adicionando nova linha?',
        top_k=3,
    )

    assert response.status == 'answer'
    assert response.answer is not None
    assert 'scd tipo 2' in response.answer.lower()
    assert 'preserva o historico completo' in response.answer.lower()


def test_answer_with_citations_trims_dangling_tail_from_partial_contract_span() -> None:
    note = _build_note(
        raw_text=(
            'de 3 (tres) anos apos o encerramento da vigencia, independentemente do motivo do\n'
            'A Contratante obriga-se a cumprir os deveres de acesso aos ambientes.\n'
        ),
        normalized_text=(
            'de 3 (tres) anos apos o encerramento da vigencia, independentemente do motivo do\n'
            'A Contratante obriga-se a cumprir os deveres de acesso aos ambientes.\n'
        ),
        structured_markdown=(
            '# Contrato\n\n'
            'de 3 (tres) anos apos o encerramento da vigencia, independentemente do motivo do\n'
            'A Contratante obriga-se a cumprir os deveres de acesso aos ambientes.\n'
        ),
        content_hash='a1' * 32,
    )

    response = answer_with_citations(
        note,
        'Qual e o prazo de confidencialidade apos o encerramento da vigencia?',
        top_k=3,
    )

    assert response.status == 'answer'
    assert response.answer is not None
    assert response.answer.lower().endswith('vigencia')
    assert not response.answer.lower().endswith('motivo do')


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


def test_extract_named_query_terms_keeps_adjacent_short_anchor() -> None:
    assert extract_named_query_terms('O que e Estrutura Disco D?') == ['Estrutura', 'Disco', 'D']


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
    assert 'debug' not in payload

    debug_result = runner.invoke(
        app,
        [
            'retrieval',
            'ask',
            str(sample_file),
            '--question',
            'O que o benchmark mede?',
            '--top-k',
            '3',
            '--debug',
        ],
    )

    assert debug_result.exit_code == 0
    debug_payload = json.loads(debug_result.stdout)
    assert debug_payload['debug']['strategy'] == 'lexical'
    assert debug_payload['debug']['hits']


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
    monkeypatch.setattr('free_plaud.retrieval.cli.get_embedder', lambda model_name, **kwargs: FakeEmbedder())

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
    monkeypatch.setattr('free_plaud.retrieval.cli.get_embedder', lambda model_name, **kwargs: FakeEmbedder())

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
