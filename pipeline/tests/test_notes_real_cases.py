from pathlib import Path

from escolio.ingest.loaders import load_document
from escolio.ingest.models import IngestedDocument
from escolio.notes.structurer import structure_document


def test_structure_document_falls_back_to_filename_when_markdown_has_only_generic_sections(
    tmp_path: Path,
) -> None:
    sample_file = tmp_path / 'Aprendizado em Camadas.md'
    sample_file.write_text(
        '## 🗂️ Sumário\n\n'
        '1. Objetivo\n'
        '2. Problema\n'
        '3. Metodologia\n\n'
        '## 🧬 Conceito-chave\n\n'
        'O aprendizado em camadas ajuda a organizar fundamentos, prática e revisão sem sobrecarregar a memória de trabalho.\n',
        encoding='utf-8',
    )

    document = load_document(sample_file)

    note = structure_document(document)

    assert note.title == 'Aprendizado em Camadas'
    assert note.summary.startswith('O aprendizado em camadas ajuda a organizar fundamentos')


def test_structure_document_prefers_intro_paragraph_over_later_blockquote_callout(
    tmp_path: Path,
) -> None:
    sample_file = tmp_path / 'Guia Essencial.md'
    sample_file.write_text(
        '# Guia Essencial para um Site de Alto Valor\n\n'
        'Este guia resume as melhores praticas de UX, UI e performance para criar sites mais claros, rapidos e valiosos para o usuario.\n\n'
        '## Tipografia\n\n'
        '> ⚠️ Atenção: se o tema for infantil, a fonte nao deve parecer formal demais. '
        'A tipografia precisa conversar com o layout, a persona e o ritmo visual da pagina.\n\n'
        'A escolha da fonte deve equilibrar legibilidade, personalidade e coerencia com a interface.\n',
        encoding='utf-8',
    )

    document = load_document(sample_file)

    note = structure_document(document)

    assert note.summary == (
        'Este guia resume as melhores praticas de UX, UI e performance para criar sites mais claros, rapidos e valiosos para o usuario.'
    )


def test_structure_document_uses_leading_blockquote_preamble_as_summary_when_document_has_no_h1(
    tmp_path: Path,
) -> None:
    sample_file = tmp_path / 'Estratégias para Lançar e Escalar um App.md'
    sample_file.write_text(
        '> Guia prático e mental map sobre como lançar, promover, monetizar e ajustar um aplicativo com foco em engajamento e fit de mercado.\n\n'
        '## 🧭 Visão Geral\n\n'
        '### Criar Clickbaits Estratégicos\n\n'
        'Dê às pessoas a sensação de que “te descobriram”.\n',
        encoding='utf-8',
    )

    document = load_document(sample_file)

    note = structure_document(document)

    assert note.title == 'Estratégias para Lançar e Escalar um App'
    assert note.summary == (
        'Guia prático e mental map sobre como lançar, promover, monetizar e ajustar um aplicativo com foco em engajamento e fit de mercado.'
    )


def test_structure_document_falls_back_to_filename_for_pdf_with_salutation_and_skips_noisy_line() -> None:
    document = IngestedDocument(
        source_path=Path('Carta de Apresentação.pdf'),
        source_type='pdf',
        raw_text=(
            'Olá,\n'
            ' sou Ricardo Andreotti\n'
            'À  e q u i p e  d e  R e c r u t a m e n t o  e  S e l e ç ã o ,\n'
            'Meu nome é Ricardo Andreotti, resido em Sorocaba, São Paulo, e busco\n'
            'constantemente o aprimoramento profissional e o desenvolvimento de novas\n'
            'competências que me permitam evoluir técnica e pessoalmente.\n'
            'Atualmente curso Ciência da Computação e desenvolvo projetos práticos com foco em software e automação.\n'
            'Atenciosamente,\n'
            'Ricardo Andreotti Gonçalves.\n'
            'Contato:\n'
            'devandreotti@gmail.com\n'
        ),
    )

    note = structure_document(document)

    assert note.title == 'Carta de Apresentação'
    assert note.summary.startswith('Meu nome é Ricardo Andreotti')
    assert 'e q u i p e' not in note.summary


def test_structure_document_prefers_resume_heading_over_contact_preamble_in_pdf() -> None:
    document = IngestedDocument(
        source_path=Path('Ricardo Andreotti - CV.pdf'),
        source_type='pdf',
        raw_text=(
            'RICARDO ANDREOTTI GONÇALVES\n'
            'Desenvolvedor Full Stack | Sorocaba - SP\n'
            '(15) 98188-8676 | devandreotti@gmail.com\n'
            'Linkedin | Github | Portfólio\n\n'
            'RESUMO PROFISSIONAL\n'
            'Estudante de Ciência da Computação com sólida base em desenvolvimento web e experiência prática em Python, React e automação.\n'
        ),
    )

    note = structure_document(document)

    assert note.title == 'RICARDO ANDREOTTI GONÇALVES'
    assert note.summary.startswith('Estudante de Ciência da Computação com sólida base')
