import json
from pathlib import Path
from typing import Self

from escolio.app.config import Settings
from escolio.ingest.loaders import load_document
from escolio.notes.extraction import (
    EXTRACTION_UNAVAILABLE_WARNING,
    NO_JSON_WARNING,
    apply_extraction,
    build_extraction_prompt,
    enrich_note,
    extract_structure,
    make_provider_llm,
)
from escolio.notes.markdown import render_note_markdown
from escolio.notes.schemas import ActionItem, Decision, NoteExtraction
from escolio.notes.structurer import structure_document

NOTE_TEXT = (
    'Reunião de planejamento do TCC.\n\n'
    'Decidimos usar ChromaDB para o índice vetorial.\n\n'
    'Maria deve revisar o capítulo de metodologia até sexta-feira.\n\n'
    'Bruno vai configurar o servidor de benchmark.\n'
)

VALID_JSON = {
    'topics': ['planejamento', 'indice vetorial'],
    'decisions': [{'text': 'Decidimos usar ChromaDB para o índice vetorial.'}],
    'action_items': [
        {'text': 'Maria deve revisar o capítulo de metodologia', 'owner': 'Maria', 'due': 'sexta-feira'},
        {'text': 'Bruno vai configurar o servidor de benchmark', 'owner': None, 'due': None},
    ],
}


class FakeLLM:
    """Devolve sempre a mesma resposta e guarda os prompts recebidos."""

    def __init__(self, response: str) -> None:
        self.response = response
        self.prompts: list[str] = []

    def __call__(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.response


def _note(tmp_path: Path, text: str = NOTE_TEXT):
    source = tmp_path / 'reuniao.txt'
    source.write_text(text, encoding='utf-8')
    return structure_document(load_document(source))


def test_valid_json_becomes_topics_decisions_and_action_items() -> None:
    llm = FakeLLM(json.dumps(VALID_JSON))

    extraction = extract_structure(NOTE_TEXT, llm)

    assert extraction.topics == ['planejamento', 'indice vetorial']
    assert [item.text for item in extraction.decisions] == [
        'Decidimos usar ChromaDB para o índice vetorial.'
    ]
    maria, bruno = extraction.action_items
    assert maria.owner == 'Maria'
    assert maria.due == 'sexta-feira'
    assert bruno.owner is None and bruno.due is None
    assert extraction.discarded == 0
    assert extraction.warnings == []
    assert 'JSON' in llm.prompts[0] and 'NOTA:' in llm.prompts[0]


def test_json_wrapped_in_fence_and_noise_is_recovered() -> None:
    raw = (
        'Claro! Aqui está a extração (versão {v2}):\n'
        '```json\n' + json.dumps(VALID_JSON, ensure_ascii=False) + '\n```\n'
        'Espero que ajude.'
    )

    extraction = extract_structure(NOTE_TEXT, FakeLLM(raw))

    assert len(extraction.decisions) == 1
    assert len(extraction.action_items) == 2
    assert extraction.warnings == []


def test_invalid_json_returns_empty_extraction_with_warning() -> None:
    extraction = extract_structure(NOTE_TEXT, FakeLLM('{"decisions": [ quebrado'))

    assert extraction.is_empty()
    assert extraction.warnings == [NO_JSON_WARNING]


def test_text_without_any_object_returns_empty_with_warning() -> None:
    extraction = extract_structure(NOTE_TEXT, FakeLLM('Não há decisões na nota.'))

    assert extraction.is_empty()
    assert extraction.warnings == [NO_JSON_WARNING]


def test_llm_exception_is_reported_as_warning_not_raised() -> None:
    def failing_llm(prompt: str) -> str:
        raise RuntimeError('Provider excedeu timeout.')

    extraction = extract_structure(NOTE_TEXT, failing_llm)

    assert extraction.is_empty()
    assert extraction.warnings == ['Extração indisponível: Provider excedeu timeout.']


def test_hallucinated_items_are_discarded_and_counted() -> None:
    payload = {
        'topics': ['tema'],
        'decisions': [
            {'text': 'Decidimos usar ChromaDB para o índice vetorial.'},
            {'text': 'Contratar consultor externo para auditoria de segurança'},
        ],
        'action_items': [
            {'text': 'Maria deve revisar o capítulo de metodologia', 'owner': 'Maria', 'due': None},
            {'text': 'Comprar licença de software proprietário Oracle', 'owner': None, 'due': 'amanhã'},
            {'text': 'Bruno vai configurar o servidor de benchmark', 'owner': 'Carlos Silva', 'due': None},
        ],
    }

    extraction = extract_structure(NOTE_TEXT, FakeLLM(json.dumps(payload)))

    assert [item.text for item in extraction.decisions] == [
        'Decidimos usar ChromaDB para o índice vetorial.'
    ]
    assert [item.text for item in extraction.action_items] == [
        'Maria deve revisar o capítulo de metodologia',
        'Bruno vai configurar o servidor de benchmark',
    ]
    assert extraction.discarded == 2
    # Responsável inventado (Carlos Silva) não aparece na nota: a tarefa fica, sem owner.
    assert extraction.action_items[1].owner is None


def test_invalid_items_are_counted_as_discarded_without_dropping_valid_ones() -> None:
    payload = {
        'decisions': [{'text': ''}, {'text': 'Decidimos usar ChromaDB para o índice vetorial.'}],
        'action_items': 'não é lista',
    }

    extraction = extract_structure(NOTE_TEXT, FakeLLM(json.dumps(payload)))

    assert len(extraction.decisions) == 1
    assert extraction.action_items == []
    assert extraction.discarded == 1


def test_min_overlap_threshold_is_configurable() -> None:
    payload = {'action_items': [{'text': 'Maria revisar relatório financeiro trimestral', 'owner': None, 'due': None}]}

    strict = extract_structure(NOTE_TEXT, FakeLLM(json.dumps(payload)), min_overlap=0.9)
    lenient = extract_structure(NOTE_TEXT, FakeLLM(json.dumps(payload)), min_overlap=0.2)

    assert strict.action_items == []
    assert [item.text for item in lenient.action_items] == ['Maria revisar relatório financeiro trimestral']


def test_default_disabled_keeps_structured_markdown_identical(tmp_path: Path) -> None:
    note = _note(tmp_path)
    before = note.structured_markdown
    llm = FakeLLM(json.dumps(VALID_JSON))

    result = enrich_note(note, Settings(extract_structure=False))

    assert result.structured_markdown == before
    assert '## Decisões' not in result.structured_markdown
    assert '## Ações' not in result.structured_markdown
    assert result.topics == [] and result.tasks == []
    assert result.extraction.is_empty()
    assert llm.prompts == []


def test_empty_extraction_renders_same_markdown_as_deterministic_note(tmp_path: Path) -> None:
    note = _note(tmp_path)
    before = note.structured_markdown

    apply_extraction(note, NoteExtraction())

    # Note strip-a espaços na atribuição (str_strip_whitespace): comparar na mesma forma.
    assert note.structured_markdown == before == render_note_markdown(note).strip()


def test_extraction_adds_decisions_and_actions_sections_and_frontmatter(tmp_path: Path) -> None:
    note = _note(tmp_path)
    extraction = extract_structure(note.normalized_text, FakeLLM(json.dumps(VALID_JSON)))

    apply_extraction(note, extraction)

    markdown = note.structured_markdown
    assert '## Decisões\n- Decidimos usar ChromaDB para o índice vetorial.' in markdown
    assert (
        '## Ações\n'
        '- Maria deve revisar o capítulo de metodologia (responsável: Maria; prazo: sexta-feira)\n'
        '- Bruno vai configurar o servidor de benchmark'
    ) in markdown
    assert markdown.index('## Raw Text') < markdown.index('## Decisões')
    assert note.topics == ['planejamento', 'indice vetorial']
    assert note.tasks[0] == 'Maria deve revisar o capítulo de metodologia (responsável: Maria; prazo: sexta-feira)'
    assert '  - indice vetorial' in markdown


def test_extraction_without_items_shows_placeholders(tmp_path: Path) -> None:
    note = _note(tmp_path)
    extraction = NoteExtraction(topics=['tema'])

    apply_extraction(note, extraction)

    assert '## Decisões\nNenhuma decisão identificada.' in note.structured_markdown
    assert '## Ações\nNenhuma ação identificada.' in note.structured_markdown


def test_action_item_label_formats_owner_and_due() -> None:
    assert ActionItem(text='Revisar').label() == 'Revisar'
    assert ActionItem(text='Revisar', owner='Ana').label() == 'Revisar (responsável: Ana)'
    assert ActionItem(text='Revisar', due='hoje').label() == 'Revisar (prazo: hoje)'
    assert Decision(text='  Usar X  ').text == 'Usar X'


def test_extractive_provider_has_no_llm_and_flag_on_warns(tmp_path: Path) -> None:
    settings = Settings(results_dir=tmp_path, answer_provider='extractive', extract_structure=True)
    note = _note(tmp_path)

    assert make_provider_llm(settings) is None
    result = enrich_note(note, settings)

    assert result.extraction.warnings == [EXTRACTION_UNAVAILABLE_WARNING]
    assert result.extraction.is_empty()


class _FakeHTTPResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode('utf-8')


def test_make_provider_llm_reuses_answer_provider_http(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    def fake_urlopen(request, timeout):
        captured['url'] = request.full_url
        captured['body'] = json.loads(request.data.decode('utf-8'))
        return _FakeHTTPResponse(
            {'choices': [{'message': {'content': json.dumps(VALID_JSON)}, 'finish_reason': 'stop'}]}
        )

    monkeypatch.setattr('escolio.providers.answer.urlopen', fake_urlopen)
    settings = Settings(
        results_dir=tmp_path,
        answer_provider='ollama',
        answer_model='qwen-pt',
        answer_base_url='http://localhost:11434/v1',
    )

    llm = make_provider_llm(settings)
    assert llm is not None
    extraction = extract_structure(NOTE_TEXT, llm)

    assert captured['url'] == 'http://localhost:11434/v1/chat/completions'
    body = captured['body']
    assert body['model'] == 'qwen-pt'
    assert body['temperature'] == 0.0
    assert body['messages'] == [{'role': 'user', 'content': build_extraction_prompt(NOTE_TEXT)}]
    assert len(extraction.decisions) == 1
