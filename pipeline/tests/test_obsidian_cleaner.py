from pathlib import Path

import pytest

from escolio.ingest.obsidian_cleaner import clean_obsidian_md, has_obsidian_signals


def test_has_obsidian_signals_detects_dataview_and_obsidian_links() -> None:
    text = (
        "```dataviewjs\n"
        "const x = dv.container;\n"
        "```\n\n"
        "[[CyberOps - SOC]]\n"
    )

    assert has_obsidian_signals(text) is True


def test_has_obsidian_signals_is_false_for_plain_markdown() -> None:
    text = "# Titulo\n\nParagrafo limpo.\n\n- item\n"

    assert has_obsidian_signals(text) is False


def test_clean_obsidian_md_preserves_plain_markdown_when_no_obsidian_noise(tmp_path: Path) -> None:
    source = tmp_path / 'plain.md'
    dest = tmp_path / 'out.md'
    source.write_text(
        '---\n'
        'type: referencia\n'
        'topic: redes\n'
        'banner: ignore.png\n'
        '---\n\n'
        '# Redes\n\n'
        'Texto limpo sobre redes.\n',
        encoding='utf-8',
    )

    clean_obsidian_md(source, dest)

    cleaned = dest.read_text(encoding='utf-8')
    assert 'type: referencia' in cleaned
    assert 'topic: redes' in cleaned
    assert 'banner:' not in cleaned
    assert '# Redes' in cleaned
    assert 'Texto limpo sobre redes.' in cleaned


def test_clean_obsidian_md_extracts_textcontent_and_innerhtml_and_removes_links(tmp_path: Path) -> None:
    source = tmp_path / 'obsidian.md'
    dest = tmp_path / 'out.md'
    source.write_text(
        '---\n'
        'type: referencia\n'
        'topic: cisco\n'
        'icon: 🛡️\n'
        'banner: test.png\n'
        '---\n\n'
        '```dataviewjs\n'
        "const t = dv.container.createEl('h2');\n"
        "t.textContent = 'SOC — Security Operations Center';\n"
        "const p = dv.container.createEl('p');\n"
        "p.innerHTML = '<p><strong>Um SOC</strong> monitora e responde incidentes.<br>Opera 24x7.</p>';\n"
        '```\n\n'
        '← [[CyberOps]] | [[CyberOps - Métricas SOC]] →\n',
        encoding='utf-8',
    )

    clean_obsidian_md(source, dest)

    cleaned = dest.read_text(encoding='utf-8')
    assert 'type: referencia' in cleaned
    assert 'topic: cisco' in cleaned
    assert 'icon:' not in cleaned
    assert 'banner:' not in cleaned
    assert 'SOC — Security Operations Center' in cleaned
    assert 'Um SOC monitora e responde incidentes.' in cleaned
    assert 'Opera 24x7.' in cleaned
    assert 'dataviewjs' not in cleaned
    assert '[[' not in cleaned
    assert '.style.cssText' not in cleaned
    assert '<strong' not in cleaned


def test_clean_obsidian_md_extracts_object_arrays_into_markdown_sections(tmp_path: Path) -> None:
    source = tmp_path / 'agents.md'
    dest = tmp_path / 'out.md'
    source.write_text(
        '```dataviewjs\n'
        'const agents = [\n'
        '  {\n'
        '    title: "Amadores (Script Kiddies)",\n'
        '    nivel: "Baixo",\n'
        '    motivacao: "Curiosidade",\n'
        '    items: [\n'
        '      "Pouca habilidade técnica",\n'
        '      "Usam ferramentas prontas"\n'
        '    ]\n'
        '  }\n'
        '];\n'
        '```\n',
        encoding='utf-8',
    )

    clean_obsidian_md(source, dest)

    cleaned = dest.read_text(encoding='utf-8')
    assert '## Amadores (Script Kiddies)' in cleaned
    assert '- Nível: Baixo' in cleaned
    assert '- Motivação: Curiosidade' in cleaned
    assert '- Pouca habilidade técnica' in cleaned
    assert '- Usam ferramentas prontas' in cleaned


def test_clean_obsidian_md_rejects_destination_inside_vault_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    vault_root = tmp_path / 'vault'
    vault_root.mkdir()
    source = vault_root / 'source.md'
    dest = vault_root / 'out.md'
    source.write_text('# teste', encoding='utf-8')

    monkeypatch.setattr('escolio.ingest.obsidian_cleaner.OBSIDIAN_VAULT_ROOT', vault_root)

    with pytest.raises(ValueError, match='Destino dentro do vault'):
        clean_obsidian_md(source, dest)


def test_clean_obsidian_md_rejects_same_source_and_destination(tmp_path: Path) -> None:
    source = tmp_path / 'same.md'
    source.write_text('# teste', encoding='utf-8')

    with pytest.raises(ValueError, match='Destino nao pode ser o mesmo arquivo'):
        clean_obsidian_md(source, source)
