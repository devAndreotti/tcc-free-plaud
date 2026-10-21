import json
from pathlib import Path

import pytest

import escolio.app.settings_catalog as escolio_settings_catalog
from escolio.app.config import USER_SETTING_FIELDS, Settings
from escolio.app.settings_catalog import (
    SETTING_SPECS,
    get_setting_spec,
    parse_catalog_value,
    save_catalog_setting,
    save_catalog_settings,
    settings_catalog_payload,
)


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        workspace_dir=tmp_path,
        data_dir=tmp_path / 'data',
        results_dir=tmp_path / 'data' / 'results',
        sqlite_path=tmp_path / 'data' / 'results' / 'escolio.sqlite3',
        vector_store_dir=tmp_path / 'data' / 'results' / 'vector_store',
        embedding_model='fake-hash',
        retrieval_top_k=4,
        default_chunk_size=800,
        default_chunk_overlap=120,
    )


def test_settings_catalog_explains_core_numbers_and_groups(tmp_path: Path) -> None:
    rows = settings_catalog_payload(_settings(tmp_path))
    by_key = {row['key']: row for row in rows}

    assert by_key['retrieval_top_k']['label'] == 'Trechos por pergunta'
    assert by_key['retrieval_top_k']['value'] == 4
    assert by_key['retrieval_top_k']['description'].startswith('Quantos trechos')
    assert by_key['default_chunk_size']['label'] == 'Tamanho do trecho'
    assert by_key['default_chunk_size']['value'] == 800
    assert by_key['default_chunk_overlap']['label'] == 'Sobreposição'
    assert by_key['default_chunk_overlap']['value'] == 120
    assert by_key['answer_api_key']['storage'] == 'local_env'
    assert by_key['answer_api_key']['secret'] is True


def test_settings_catalog_marks_simple_and_advanced_layers(tmp_path: Path) -> None:
    rows = settings_catalog_payload(_settings(tmp_path))
    by_key = {row['key']: row for row in rows}

    assert by_key['default_corpus_path']['layer'] == 'simple'
    assert by_key['corpus_recursive_default']['layer'] == 'simple'
    assert by_key['embedding_device']['layer'] == 'simple'
    assert by_key['default_ask_strategy']['layer'] == 'simple'
    assert by_key['answer_provider']['layer'] == 'simple'
    assert by_key['answer_model']['layer'] == 'simple'
    assert by_key['answer_api_key']['layer'] == 'simple'
    assert by_key['retrieval_top_k']['layer'] == 'advanced'
    assert by_key['default_chunk_size']['layer'] == 'advanced'
    assert by_key['default_chunk_overlap']['layer'] == 'advanced'
    assert by_key['corpus_commit_mode']['layer'] == 'advanced'
    assert by_key['corpus_embedding_batch_size']['layer'] == 'advanced'
    assert by_key['corpus_index_workers']['layer'] == 'advanced'
    assert by_key['answer_base_url']['layer'] == 'advanced'
    assert by_key['answer_temperature']['layer'] == 'advanced'
    assert by_key['answer_timeout_seconds']['layer'] == 'advanced'
    assert by_key['answer_max_tokens']['layer'] == 'advanced'


def test_settings_catalog_warns_when_embedding_model_is_fake_hash(tmp_path: Path) -> None:
    rows = settings_catalog_payload(_settings(tmp_path))
    embedding = next(row for row in rows if row['key'] == 'embedding_model')

    assert embedding['warning'] == 'fake-hash é modelo de teste; use chroma-default ou sentence-transformer real.'


def test_save_catalog_setting_uses_user_settings_or_local_env(tmp_path: Path, monkeypatch) -> None:
    settings = _settings(tmp_path)
    monkeypatch.delenv('ESCOLIO_ANSWER_API_KEY', raising=False)

    save_catalog_setting('retrieval_top_k', '7', settings=settings)
    save_catalog_setting('answer_api_key', 'sk-catalog-test', settings=settings)

    payload = json.loads((tmp_path / 'data' / 'results' / 'user_settings.json').read_text(encoding='utf-8'))
    assert payload['retrieval_top_k'] == 7
    assert 'answer_api_key' not in payload
    assert 'ESCOLIO_ANSWER_API_KEY=sk-catalog-test' in (tmp_path / 'pipeline' / '.env').read_text(encoding='utf-8')


def test_save_catalog_setting_accepts_audio_fields(tmp_path: Path) -> None:
    settings = _settings(tmp_path)

    save_catalog_setting('audio_model', 'moonshine-tiny-en', settings=settings)
    save_catalog_setting('audio_language', 'en', settings=settings)
    save_catalog_setting('audio_device', 'cpu', settings=settings)

    payload = json.loads((tmp_path / 'data' / 'results' / 'user_settings.json').read_text(encoding='utf-8'))
    assert payload['audio_model'] == 'moonshine-tiny-en'
    assert payload['audio_language'] == 'en'
    assert payload['audio_device'] == 'cpu'


def test_save_catalog_settings_batches_multiple_keys_in_one_write(tmp_path: Path, monkeypatch) -> None:
    settings = _settings(tmp_path)
    monkeypatch.delenv('ESCOLIO_ANSWER_API_KEY', raising=False)
    write_calls = []
    real_save_user_settings = escolio_settings_catalog.save_user_settings

    def counting_save_user_settings(values, *, settings=None):
        write_calls.append(dict(values))
        return real_save_user_settings(values, settings=settings)

    monkeypatch.setattr(escolio_settings_catalog, 'save_user_settings', counting_save_user_settings)

    save_catalog_settings(
        {
            'retrieval_top_k': '7',
            'default_chunk_size': '500',
            'default_chunk_overlap': '50',
            'answer_api_key': 'sk-batch-test',
        },
        settings=settings,
    )

    assert len(write_calls) == 1
    payload = json.loads((tmp_path / 'data' / 'results' / 'user_settings.json').read_text(encoding='utf-8'))
    assert payload['retrieval_top_k'] == 7
    assert payload['default_chunk_size'] == 500
    assert payload['default_chunk_overlap'] == 50
    assert 'answer_api_key' not in payload
    assert 'ESCOLIO_ANSWER_API_KEY=sk-batch-test' in (tmp_path / 'pipeline' / '.env').read_text(encoding='utf-8')


def test_save_catalog_settings_rejects_invalid_pair_together(tmp_path: Path) -> None:
    settings = _settings(tmp_path)

    with pytest.raises(ValueError) as caught:
        save_catalog_settings(
            {'default_chunk_size': '100', 'default_chunk_overlap': '500'},
            settings=settings,
        )
    message = str(caught.value)
    assert 'validation error' not in message.lower(), 'mensagem nao deve vazar o dump verboso do pydantic'
    assert 'default_chunk' in message


def test_save_catalog_settings_reports_key_in_parse_error(tmp_path: Path) -> None:
    settings = _settings(tmp_path)

    with pytest.raises(ValueError, match='retrieval_top_k'):
        save_catalog_settings({'retrieval_top_k': 'nao-e-numero'}, settings=settings)


def test_parse_catalog_value_treats_whitespace_only_as_blank() -> None:
    spec = get_setting_spec('retrieval_top_k')
    assert parse_catalog_value(spec, '   ') is None


def test_warns_when_default_corpus_path_does_not_exist(tmp_path: Path) -> None:
    settings = _settings(tmp_path).model_copy(update={'default_corpus_path': tmp_path / 'nao-existe'})
    rows = settings_catalog_payload(settings)
    row = next(row for row in rows if row['key'] == 'default_corpus_path')

    assert row['warning'] is not None
    assert row['warning'].startswith('Pasta não encontrada: ')


def test_warns_when_audio_language_incompatible_with_audio_model(tmp_path: Path) -> None:
    settings = _settings(tmp_path).model_copy(update={'audio_model': 'moonshine-tiny-en', 'audio_language': 'pt'})
    rows = settings_catalog_payload(settings)
    row = next(row for row in rows if row['key'] == 'audio_language')

    assert row['warning'] is not None
    assert 'moonshine-tiny-en' in row['warning']


def test_no_audio_language_warning_when_compatible(tmp_path: Path) -> None:
    settings = _settings(tmp_path).model_copy(update={'audio_model': 'whisper-small', 'audio_language': 'auto'})
    rows = settings_catalog_payload(settings)
    row = next(row for row in rows if row['key'] == 'audio_language')

    assert row['warning'] is None


def test_numeric_settings_expose_min_max_from_pydantic_constraints(tmp_path: Path) -> None:
    rows = settings_catalog_payload(_settings(tmp_path))
    by_key = {row['key']: row for row in rows}

    assert by_key['retrieval_top_k']['min'] == 1
    assert by_key['retrieval_top_k']['max'] == 50
    assert by_key['default_chunk_size']['min'] == 100
    assert by_key['default_chunk_size']['max'] == 4000
    assert by_key['answer_temperature']['min'] == 0.0
    assert by_key['answer_temperature']['max'] == 2.0
    assert by_key['embedding_model']['min'] is None
    assert by_key['embedding_model']['max'] is None


def test_audio_language_options_come_from_catalog() -> None:
    spec = get_setting_spec('audio_language')
    values = {option.value for option in spec.options}

    assert spec.value_type == 'enum'
    assert 'auto' in values
    # Idiomas reais suportados pelo whisper-small no catalogo (audio_catalog.py).
    assert {'pt', 'en', 'es'} <= values


def test_user_setting_fields_covers_all_catalog_specs() -> None:
    catalog_keys = {spec.key for spec in SETTING_SPECS if spec.storage == 'user_settings'}
    missing = catalog_keys - USER_SETTING_FIELDS
    assert not missing, f'Specs em user_settings sem chave registrada em USER_SETTING_FIELDS: {missing}'


def test_get_setting_spec_rejects_unknown_key() -> None:
    assert get_setting_spec('retrieval_top_k').value_type == 'int'
    try:
        get_setting_spec('missing')
    except KeyError as exc:
        assert 'missing' in str(exc)
    else:
        raise AssertionError('missing setting deveria falhar')


def test_audio_input_device_lists_connected_mics_and_flags_missing_saved_one(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(escolio_settings_catalog, 'list_input_devices', lambda: ['Headset (QCY H3 Pro)'])
    settings = _settings(tmp_path).model_copy(update={'audio_input_device': 'Mic sumiu'})

    row = next(r for r in settings_catalog_payload(settings) if r['key'] == 'audio_input_device')

    assert row['options'] == [
        {'value': '', 'label': 'Padrão do sistema'},
        {'value': 'Headset (QCY H3 Pro)', 'label': 'Headset (QCY H3 Pro)'},
        {'value': 'Mic sumiu', 'label': 'Mic sumiu (não encontrado)'},
    ]
    assert row['warning'] == 'Microfone "Mic sumiu" não está conectado; a gravação vai falhar até reconectar ou escolher outro.'


def test_audio_input_device_keeps_only_default_when_listing_fails(tmp_path: Path, monkeypatch) -> None:
    def unavailable() -> list[str]:
        raise OSError('PortAudio ausente')

    monkeypatch.setattr(escolio_settings_catalog, 'list_input_devices', unavailable)
    settings = _settings(tmp_path).model_copy(update={'audio_input_device': 'Headset'})

    row = next(r for r in settings_catalog_payload(settings) if r['key'] == 'audio_input_device')

    assert row['options'] == [{'value': '', 'label': 'Padrão do sistema'}]
    assert row['warning'] is None


def test_opcoes_tecnicas_trazem_explicacao_para_o_usuario(tmp_path: Path) -> None:
    # Provedor de resposta e devices explicam cada opção (Extractive, Ollama, Auto, CPU, CUDA...).
    rows = {r['key']: r for r in settings_catalog_payload(_settings(tmp_path))}

    for key in ('answer_provider', 'audio_device', 'embedding_device', 'default_ask_strategy', 'corpus_commit_mode'):
        assert all(option.get('description') for option in rows[key]['options']), key
    providers = {option['value']: option['description'] for option in rows['answer_provider']['options']}
    assert 'offline' in providers['extractive']
    assert 'localhost:11434' in providers['ollama']
    # Opções sem explicação continuam sem a chave (formato antigo).
    assert all('description' not in option for option in rows['audio_language']['options'])


def test_save_catalog_settings_rejects_base_url_without_http_scheme(tmp_path: Path) -> None:
    settings = _settings(tmp_path)

    with pytest.raises(ValueError, match='answer_base_url'):
        save_catalog_settings({'answer_base_url': 'exemplo.test/v1'}, settings=settings)
    assert not (tmp_path / 'data' / 'results' / 'user_settings.json').exists()

    save_catalog_settings({'answer_base_url': 'https://exemplo.test/v1'}, settings=settings)
    payload = json.loads((tmp_path / 'data' / 'results' / 'user_settings.json').read_text(encoding='utf-8'))
    assert payload['answer_base_url'] == 'https://exemplo.test/v1'


def test_warns_when_global_embedding_model_differs_from_active_vault(tmp_path: Path, monkeypatch) -> None:
    active = _settings(tmp_path).model_copy(update={'embedding_model': 'chroma-default'})
    global_settings = active.model_copy(update={'embedding_model': 'sentence-transformer:modelo-global'})
    monkeypatch.setattr(escolio_settings_catalog, 'base_settings', lambda: global_settings)

    row = next(r for r in settings_catalog_payload(active) if r['key'] == 'embedding_model')

    assert row['warning'] is not None
    assert 'modelo-global' in row['warning']

    monkeypatch.setattr(escolio_settings_catalog, 'base_settings', lambda: active)

    row = next(r for r in settings_catalog_payload(active) if r['key'] == 'embedding_model')

    assert row['warning'] is None


def test_warns_when_cuda_is_selected_but_unavailable(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr('escolio.providers.embed._cuda_available', lambda: False)
    settings = _settings(tmp_path).model_copy(
        update={'embedding_model': 'sentence-transformer:modelo-teste', 'embedding_device': 'cuda'}
    )

    row = next(r for r in settings_catalog_payload(settings) if r['key'] == 'embedding_device')

    assert row['warning'] is not None
    assert 'CUDA indisponível' in row['warning']
