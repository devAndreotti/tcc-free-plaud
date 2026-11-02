from pathlib import Path

import pytest

from escolio.ingest.loaders import load_document
from escolio.notes.normalizer import looks_like_fragmented_ocr, normalize_text
from escolio.notes.structurer import structure_document

OCR_DOC = (
    'RELA TÓRIO DE AVALI AÇÃO DE FERRAMENTAS\n'
    'DE MONITORAMENTO DE INFRA ESTRUTURA\n'
    'Versão: 2 .1\n'
    'Data : 14 /fev/ 2025\n'
    '\n'
    '1. OBJ ETIVO\n'
    '\n'
    'ANEXO II — API REST\n'
)


@pytest.mark.parametrize(
    'line',
    [
        # Regressão: linhas reais que o reparo de OCR colava ("Theuser", "Nãohá", "forc intext", "ANEXOI").
        'The user can express any of the intents below in plain English —',
        'match the intent to the tool. They do not need to name the tool.',
        '| "give me the stats" / structured snapshot for the agent to consume |',
        'Não há SonarCloud nem gate de Docker: a análise de qualidade é o gate.',
        'Apresenta boa coerência local, mas perde contexto inter-sentencial.',
        'text = "".join(c for c in text if unicodedata.category(c) != "Mn")',
        'x = a if b else c ; y : int = 1 ; z = d ? e : f',
        'ANEXO I — ESPECIFICAÇÕES TÉCNICAS',
        '## API REST',
        'SQL SERVER',
    ],
)
def test_nota_comum_nao_tem_palavra_colada_nem_espaco_removido(line: str) -> None:
    assert normalize_text(f'Antes.\n{line}\nDepois.') == f'Antes.\n{line}\nDepois.'


def test_linha_que_comeca_com_pontuacao_nao_cola_na_anterior() -> None:
    text = 'Rode o script:\n./run.sh\n.env fica fora do git'
    assert normalize_text(text) == text


def test_documento_com_ocr_fragmentado_e_reparado() -> None:
    assert looks_like_fragmented_ocr(OCR_DOC)
    lines = normalize_text(OCR_DOC).splitlines()

    assert lines[0] == 'RELATÓRIO DE AVALIAÇÃO DE FERRAMENTAS'
    assert lines[1] == 'DE MONITORAMENTO DE INFRAESTRUTURA'
    assert lines[2] == 'Versão: 2.1'
    assert lines[3] == 'Data: 14/fev/ 2025'
    assert '1. OBJETIVO' in lines
    # Numeral romano e sigla ficam inteiros mesmo em documento com OCR.
    assert 'ANEXO II — API REST' in lines


def test_duas_linhas_em_caixa_alta_nao_bastam_para_marcar_como_ocr() -> None:
    text = 'PLANO ANUAL\nTexto da nota.\nTERMO ADITIVO\nMais texto.'
    assert not looks_like_fragmented_ocr(text)
    assert normalize_text(text) == text


@pytest.mark.parametrize(
    'text',
    [
        # Regressão: licença e SQL em maiúsculas viravam "NOTCREATE", "BELIABLE" e "ONUPDATE".
        (
            'THE FONT SOFTWARE IS PROVIDED "AS IS"\n'
            'COPYRIGHT HOLDER BE LIABLE FOR ANY CLAIM\n'
            'LEGAL SERVICES. DOCUMENT DOES NOT CREATE\n'
            'Copyright 2024.\n'
        ),
        'CREATE TABLE T (\n  ID INT NOT NULL DEFAULT 30,\n  EM DATETIME ON UPDATE NOW\n)\nLEFT JOIN OUTRA v ON t.ID = v.ID\n',
    ],
)
def test_caixa_alta_sem_espaco_de_ocr_nao_e_reparada(text: str) -> None:
    assert not looks_like_fragmented_ocr(text)
    assert normalize_text(text) == text.strip()


def test_resumo_de_nota_comum_nao_cola_palavras(tmp_path: Path) -> None:
    source = tmp_path / 'nota.md'
    frase = 'The user can express any of the intents below and do not need to name it in the app.'
    source.write_text(f'# Ferramentas\n\n{frase}\n', encoding='utf-8')

    note = structure_document(load_document(source))

    assert note.summary.startswith('The user can express any of the intents')
    assert frase in note.normalized_text
