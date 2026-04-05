import json
from pathlib import Path

from typer.testing import CliRunner

from free_plaud.app.config import Settings
from free_plaud.cli import app
from free_plaud.ingest.loaders import load_document
from free_plaud.notes.metadata import build_note_id
from free_plaud.notes.repository import save_note_locally
from free_plaud.notes.structurer import structure_document

runner = CliRunner()


def test_build_note_id_normalizes_accents_and_trailing_spaces() -> None:
    path = Path('Requisitos funcionais e requisitos de negócio do projeto .md')

    note_id = build_note_id(path)

    assert note_id == 'requisitos-funcionais-e-requisitos-de-negocio-do-projeto'


def test_structure_document_builds_consistent_note_from_markdown(sample_markdown_file: Path) -> None:
    document = load_document(sample_markdown_file)

    note = structure_document(document)

    assert note.note_id == 'sample'
    assert note.note_version == 1
    assert note.source_type == 'md'
    assert note.source_name == 'sample.md'
    assert note.title == 'Titulo da Nota'
    assert 'Resumo em markdown para validar a estruturacao.' in note.summary
    assert note.raw_text == document.raw_text
    assert note.normalized_text == document.raw_text.strip()
    assert len(note.content_hash) == 64
    assert note.structured_markdown
    assert note.structured_markdown != note.raw_text


def test_structured_markdown_contains_frontmatter_and_sections(sample_text_file: Path) -> None:
    document = load_document(sample_text_file)

    note = structure_document(document)

    assert note.structured_markdown.startswith('---\n')
    assert 'note_id: sample' in note.structured_markdown
    assert 'note_version: 1' in note.structured_markdown
    assert 'source_type: txt' in note.structured_markdown
    assert 'source_name: sample.txt' in note.structured_markdown
    assert '## Summary' in note.structured_markdown
    assert '## Normalized Text' in note.structured_markdown
    assert '## Raw Text' in note.structured_markdown
    assert 'Arquitetura de benchmark local-first' in note.structured_markdown


def test_structure_document_uses_first_real_paragraph_as_summary(tmp_path: Path) -> None:
    sample_file = tmp_path / 'doc.md'
    sample_file.write_text(
        '# Documento\n\n'
        '## Objetivo deste documento\n\n'
        '| Coluna | Valor |\n'
        '| --- | --- |\n'
        '| A | B |\n\n'
        '- item solto\n\n'
        'Este paragrafo deve virar o resumo inicial da nota.\n\n'
        'Outro paragrafo complementar.\n',
        encoding='utf-8',
    )

    document = load_document(sample_file)

    note = structure_document(document)

    assert note.summary == 'Este paragrafo deve virar o resumo inicial da nota.'


def test_structure_document_prefers_markdown_h1_after_leading_table(tmp_path: Path) -> None:
    sample_file = tmp_path / 'anotacoes.md'
    sample_file.write_text(
        '| topico | status |\n'
        '| --- | --- |\n'
        '| estudar | pendente |\n\n'
        '# Anotacoes da semana\n\n'
        'Resumo mais util da semana com contexto real do que aconteceu.\n',
        encoding='utf-8',
    )

    document = load_document(sample_file)

    note = structure_document(document)

    assert note.title == 'Anotacoes da semana'
    assert note.summary == 'Resumo mais util da semana com contexto real do que aconteceu.'


def test_structure_document_prefers_summary_under_preferred_markdown_section(tmp_path: Path) -> None:
    sample_file = tmp_path / 'relatorio.md'
    sample_file.write_text(
        '# Relatorio de Benchmark\n\n'
        '**Tipo:** Relatorio tecnico interno\n'
        '**Autor:** Equipe X\n\n'
        '## Sumario Executivo\n\n'
        'Este relatorio apresenta os principais resultados do benchmark e justifica a escolha do modelo.\n\n'
        '## Metodologia\n\n'
        'Texto secundario.\n',
        encoding='utf-8',
    )

    document = load_document(sample_file)

    note = structure_document(document)

    assert note.summary == (
        'Este relatorio apresenta os principais resultados do benchmark e justifica a escolha do modelo.'
    )


def test_structure_document_skips_metadata_lines_in_plain_text_summary(tmp_path: Path) -> None:
    sample_file = tmp_path / 'ata.txt'
    sample_file.write_text(
        'ATA DE REUNIAO - SPRINT 14\n'
        'Data: 18 de marco de 2025\n'
        'Horario: 09h00 as 10h30\n'
        'OBJETIVO DA REUNIAO\n'
        'Definir o escopo da sprint e alinhar prioridades com base no feedback do cliente.\n',
        encoding='utf-8',
    )

    document = load_document(sample_file)

    note = structure_document(document)

    assert note.title == 'ATA DE REUNIAO - SPRINT 14'
    assert note.summary == 'Definir o escopo da sprint e alinhar prioridades com base no feedback do cliente.'


def test_structure_document_falls_back_to_humanized_filename_for_generic_heading(tmp_path: Path) -> None:
    sample_file = tmp_path / 'requisitos_projeto .md'
    sample_file.write_text(
        '## requisitos\n\n'
        '### nao funcionais\n\n'
        'O sistema deve operar localmente e permitir integracao com o ERP legado.\n',
        encoding='utf-8',
    )

    document = load_document(sample_file)

    note = structure_document(document)

    assert note.title == 'requisitos projeto'
    assert note.summary == 'O sistema deve operar localmente e permitir integracao com o ERP legado.'


def test_structure_document_prefers_objective_section_over_participants_in_minutes(tmp_path: Path) -> None:
    sample_file = tmp_path / 'ata_completa.txt'
    sample_file.write_text(
        'ATA DE COMITE DE ARQUITETURA - SESSAO 07/2025\n\n'
        'Documento: ACT-2025-07\n'
        'Tipo: Ata de Reuniao Tecnica\n'
        'Data: 25 de marco de 2025\n\n'
        'PARTICIPANTES\n'
        'Marcos Vinicius Teixeira - Arquiteto-Chefe\n'
        'Priscila Alencar - Engenheira de Plataforma\n'
        'Juliana Ramos - Gerente de Produto\n\n'
        'OBJETIVO DA SESSAO\n\n'
        'Avaliar as propostas tecnicas para adocao de um message broker na plataforma e tomar uma decisao formal com documentacao em ADR.\n',
        encoding='utf-8',
    )

    document = load_document(sample_file)

    note = structure_document(document)

    assert note.summary == (
        'Avaliar as propostas tecnicas para adocao de um message broker na plataforma e tomar uma decisao formal com documentacao em ADR.'
    )


def test_structure_document_prefers_more_informative_paragraph_over_short_fragment(tmp_path: Path) -> None:
    sample_file = tmp_path / 'fragmentado.txt'
    sample_file.write_text(
        'docker e containers - estudos\n\n'
        'o que e container?\n\n'
        'processo isolado\n'
        'namespaces + cgroups\n'
        'nao e VM\n\n'
        'um trecho importante\n\n'
        'O modelo de camadas das imagens Docker e uma das caracteristicas mais elegantes do sistema. '
        'Cada instrucao no Dockerfile cria uma nova camada somente leitura, o que economiza espaco em disco '
        'e acelera a inicializacao de containers em relacao a maquinas virtuais tradicionais.\n',
        encoding='utf-8',
    )

    document = load_document(sample_file)

    note = structure_document(document)

    assert note.summary.startswith('O modelo de camadas das imagens Docker')


def test_structure_document_skips_visual_page_noise_from_pdf_like_text(tmp_path: Path) -> None:
    sample_file = tmp_path / 'contrato.txt'
    sample_file.write_text(
        'CONTRATO DE PRESTACAO DE SERVICOS TECNICOS ESPECIALIZADOS No 2025/0047\n'
        'CONTRATO DE PRESTACAO DE SERVICOS TECNICOS ESPECIALIZADOS No 2025/0047\n\n'
        '────────────────────────────────────────────────────────────────\n'
        'Sistema de Gestao Documental v3.1 | Confidencial | Pag. 1 de 8\n'
        '────────────────────────────────────────────────────────────────\n\n'
        'CLAUSULA 1 - DO OBJETO\n\n'
        'O presente contrato tem por objeto a prestacao de servicos tecnicos especializados em desenvolvimento de software, '
        'manutencao evolutiva e suporte tecnico de primeiro e segundo niveis para os sistemas de gestao interna da Contratante.\n',
        encoding='utf-8',
    )

    document = load_document(sample_file)

    note = structure_document(document)

    assert note.summary.startswith('O presente contrato tem por objeto a prestacao de servicos tecnicos especializados')


def test_structure_document_repairs_light_ocr_fragmentation_in_title_and_summary(tmp_path: Path) -> None:
    sample_file = tmp_path / 'ocr.txt'
    sample_file.write_text(
        'RELA TORIO DE AVALI ACAO DE FERRAMENTAS\n'
        'DE MONITORAMENTO DE INFRA ESTRUTURA\n'
        'Versao: 2 .1\n\n'
        '1. OBJ ETIVO\n\n'
        'Este relat orio apr esenta os resultados da avali acao comparativa de tres ferramentas de monitoramento de infra estrutura.\n',
        encoding='utf-8',
    )

    document = load_document(sample_file)

    note = structure_document(document)

    assert note.title == 'RELATORIO DE AVALIACAO DE FERRAMENTAS DE MONITORAMENTO DE INFRAESTRUTURA'
    assert note.summary.startswith('Este relatorio apresenta os resultados da avaliacao comparativa')


def test_structure_document_does_not_choose_code_block_as_summary(tmp_path: Path) -> None:
    sample_file = tmp_path / 'codigo.md'
    sample_file.write_text(
        '# Implementacao de Pipeline de Ingestao\n\n'
        'Abaixo esta a implementacao inicial do modulo de ingestao. O codigo foi escrito na fase de prototipagem.\n\n'
        '```python\n'
        'def slugify(title: str) -> str:\n'
        '    text = title.lower()\n'
        '    return text.replace(\" \", \"-\")\n'
        '```\n\n'
        'Este modulo implementa leitura de arquivo, normalizacao de texto e geracao de slug.\n',
        encoding='utf-8',
    )

    document = load_document(sample_file)

    note = structure_document(document)

    assert note.summary == 'Abaixo esta a implementacao inicial do modulo de ingestao. O codigo foi escrito na fase de prototipagem.'


def test_notes_build_cli_renders_structured_markdown(sample_markdown_file: Path) -> None:
    result = runner.invoke(app, ['notes', 'build', str(sample_markdown_file)])

    assert result.exit_code == 0
    assert '# Titulo da Nota' in result.stdout
    assert '## Summary' in result.stdout


def test_notes_build_cli_accepts_unquoted_path_with_spaces(tmp_path: Path) -> None:
    sample_file = tmp_path / 'nota com espacos.md'
    sample_file.write_text('# Nota com espacos\n\nConteudo.\n', encoding='utf-8')

    result = runner.invoke(app, ['notes', 'build', *str(sample_file).split(' ')])

    assert result.exit_code == 0
    assert '# Nota com espacos' in result.stdout


def test_save_note_locally_persists_markdown_and_manifest(sample_markdown_file: Path, tmp_path: Path) -> None:
    document = load_document(sample_markdown_file)
    note = structure_document(document)
    settings = Settings(
        workspace_dir=tmp_path,
        data_dir=tmp_path / 'data',
        notes_dir=tmp_path / 'data' / 'corpus' / 'notes',
        datasets_dir=tmp_path / 'data' / 'datasets',
        results_dir=tmp_path / 'data' / 'results',
        sqlite_path=tmp_path / 'data' / 'results' / 'free_plaud.sqlite3',
        vector_store_dir=tmp_path / 'data' / 'results' / 'vector_store',
    )

    artifact = save_note_locally(note, settings.notes_dir)

    assert artifact.note_path == settings.notes_dir / 'sample.md'
    assert artifact.meta_path == settings.notes_dir / 'sample.meta.json'
    assert artifact.note_path.exists()
    assert artifact.meta_path.exists()
    assert artifact.note_path.read_text(encoding='utf-8').startswith('---\n')
    metadata = json.loads(artifact.meta_path.read_text(encoding='utf-8'))
    assert metadata['note_id'] == 'sample'
    assert metadata['source_name'] == 'sample.md'
    assert metadata['content_hash'] == note.content_hash
    assert len(metadata['structured_hash']) == 64


def test_notes_save_cli_persists_note_using_configured_notes_dir(
    sample_markdown_file: Path,
    monkeypatch,
    tmp_path: Path,
) -> None:
    settings = Settings(
        workspace_dir=tmp_path,
        data_dir=tmp_path / 'data',
        notes_dir=tmp_path / 'data' / 'corpus' / 'notes',
        datasets_dir=tmp_path / 'data' / 'datasets',
        results_dir=tmp_path / 'data' / 'results',
        sqlite_path=tmp_path / 'data' / 'results' / 'free_plaud.sqlite3',
        vector_store_dir=tmp_path / 'data' / 'results' / 'vector_store',
    )
    monkeypatch.setattr('free_plaud.notes.cli.get_settings', lambda: settings)

    result = runner.invoke(app, ['notes', 'save', str(sample_markdown_file)])

    assert result.exit_code == 0
    assert 'note_path' in result.stdout
    assert 'meta_path' in result.stdout
    assert (settings.notes_dir / 'sample.md').exists()
    assert (settings.notes_dir / 'sample.meta.json').exists()
