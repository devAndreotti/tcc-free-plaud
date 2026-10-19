from pathlib import Path

import pytest

from escolio.app.config import Settings
from escolio.app.conversations import load_conversations, save_conversations

PAYLOAD = {
    'tabs': [{'id': 'aba-1', 'label': 'Redes', 'type': 'chat', 'vaultId': 'obsidian'}],
    'activeTabId': 'aba-1',
    'tabMessages': {
        'aba-1': [
            {'id': 'msg-1', 'role': 'user', 'content': 'Qual broker foi adotado?', 'timestamp': '2026-10-19T10:00:00.000Z'},
        ],
    },
}


def _settings(tmp_path: Path) -> Settings:
    return Settings(results_dir=tmp_path)


def test_salva_e_le_de_volta_sem_deixar_tmp(tmp_path: Path) -> None:
    settings = _settings(tmp_path)

    save_conversations(PAYLOAD, settings=settings)

    assert load_conversations(settings=settings) == PAYLOAD
    assert (tmp_path / 'conversations.json').exists()
    assert not (tmp_path / 'conversations.json.tmp').exists()


def test_sem_arquivo_devolve_none(tmp_path: Path) -> None:
    assert load_conversations(settings=_settings(tmp_path)) is None


@pytest.mark.parametrize(
    'conteudo',
    ['{nao e json', '[1, 2, 3]', '{"tabs": "x", "activeTabId": null, "tabMessages": {}}'],
)
def test_arquivo_corrompido_ou_invalido_devolve_none(tmp_path: Path, conteudo: str) -> None:
    settings = _settings(tmp_path)
    (tmp_path / 'conversations.json').write_text(conteudo, encoding='utf-8')

    assert load_conversations(settings=settings) is None


@pytest.mark.parametrize(
    'payload',
    [
        ['lista', 'nao', 'objeto'],
        {'activeTabId': None, 'tabMessages': {}},
        {'tabs': {}, 'activeTabId': None, 'tabMessages': {}},
        {'tabs': [], 'tabMessages': {}},
        {'tabs': [], 'activeTabId': 0, 'tabMessages': {}},
        {'tabs': [], 'activeTabId': None, 'tabMessages': []},
    ],
)
def test_payload_invalido_levanta_value_error_e_nao_grava(tmp_path: Path, payload: object) -> None:
    with pytest.raises(ValueError):
        save_conversations(payload, settings=_settings(tmp_path))

    assert not (tmp_path / 'conversations.json').exists()


def test_payload_acima_do_limite_levanta_value_error(tmp_path: Path) -> None:
    grande = {'tabs': [], 'activeTabId': None, 'tabMessages': {'x': [{'content': 'a' * (5 * 1024 * 1024)}]}}

    with pytest.raises(ValueError, match='5 MB'):
        save_conversations(grande, settings=_settings(tmp_path))


def test_salvamento_recusado_nao_troca_o_arquivo_bom(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    save_conversations(PAYLOAD, settings=settings)

    with pytest.raises(ValueError):
        save_conversations({'tabs': 'x', 'activeTabId': None, 'tabMessages': {}}, settings=settings)

    assert load_conversations(settings=settings) == PAYLOAD
