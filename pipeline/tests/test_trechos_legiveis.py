import time
from pathlib import Path

from escolio.corpus.ask import _build_corpus_claims, _citation_from_corpus_hit
from escolio.ingest.loaders import load_document
from escolio.notes.readable import readable_chunk_text
from escolio.notes.structurer import structure_document
from escolio.retrieval.models import Chunk, SearchHit
from escolio.retrieval.search import normalize_query_terms

# Chunk 0 de uma nota do Obsidian: frontmatter, callout, wikilinks e bloco dataviewjs.
CHUNK_CISCO = (
    '---\ntype: index\narea: ti\ntopic: cisco\nstatus: ativo\ncreated: 2026-01-05\nupdated: 2026-04-17\ntags:\n'
    '  - area/ti\n  - tema/cisco\n  - tipo/index\n\nbanner: Imagens/Banner/pixel-art.jpg\nicon: 🌐\nbanner-display: cover\n---\n\n'
    '>[!info] **Cisco — Trilha de Cursos e Certificações**\n'
    'Este arquivo centraliza os cursos em [[Switch|switches]] e [[VLAN#Resumo]].\n\n'
    '```dataviewjs\ndv.table(["Nome"], dv.pages())\n```\n'
)

# Nota sem H1, com callout vazio ("[!note]") e wikilinks no fim.
CHUNK_VLAN = (
    '---\ntype: conceito\narea: ti\ntags:\n  - area/ti\n  - tema/conceitos\n---\n\n'
    '# VLAN\n\n> [!note]\n> Stub criado para fechar a navegação do índice de conceitos.\n\n'
    '## Resumo\n\n- Adicione segmentação lógica, isolamento e trunk/access.\n\n'
    '## Relacionados\n\n- [[Switch]]\n'
)


def _hit(chunk_id: str, text: str) -> SearchHit:
    chunk = Chunk(
        chunk_id=chunk_id,
        note_id='nota',
        note_version=1,
        chunk_index=0,
        char_start=0,
        char_end=len(text),
        chunk_size=800,
        overlap=120,
        chunk_text=text,
        token_count=len(text.split()),
        strategy='fixed_char_window',
        normalized_text_sha256=f'{chunk_id}-normalized',
        text_sha256=f'{chunk_id}-text',
        pipeline_version='test',
    )
    return SearchHit(chunk=chunk, score=1.0, term_coverage=1.0, strategy='lexical')


def test_readable_chunk_text_remove_frontmatter_callout_wikilink_e_dataview() -> None:
    assert readable_chunk_text(CHUNK_CISCO) == (
        '**Cisco — Trilha de Cursos e Certificações**\n'
        'Este arquivo centraliza os cursos em switches e VLAN.'
    )


def test_readable_chunk_text_nao_apaga_lista_ou_chave_valor_antes_de_regra_horizontal() -> None:
    # Regressão: "parece YAML" no começo do trecho não é frontmatter (só o bloco aberto por --- no início da nota é).
    lista = '- Instale o Docker\n- Rode o compose\n\n---\n\n## Próximos passos'
    ata = 'Status: aprovado pelo cliente\nPrazo: 30 dias\n---\nResto da ata.'

    assert readable_chunk_text(lista) == lista
    assert readable_chunk_text(ata) == ata


def test_frontmatter_sem_fecho_com_lista_longa_nao_trava() -> None:
    # Regressão: trecho cortado no meio de um frontmatter grande (sem o --- de fecho) levava 2^n passos; 24 itens eram ~30 s.
    chunk = '---\ntags:\n' + '  - item\n' * 24 + 'texto da nota'

    start = time.perf_counter()
    assert readable_chunk_text(chunk).endswith('texto da nota')
    assert time.perf_counter() - start < 1.0


def test_readable_chunk_text_mantem_regra_horizontal_depois_de_prosa() -> None:
    chunk = 'Primeira frase do trecho.\n\n---\n\nSegunda frase, com [[Alvo]].'

    assert readable_chunk_text(chunk) == 'Primeira frase do trecho.\n\n---\n\nSegunda frase, com Alvo.'


def test_claims_do_chunk_com_frontmatter_callout_e_wikilink_saem_legiveis() -> None:
    question = 'Qual trilha cisco existe?'

    claims = _build_corpus_claims(question, [_hit('cisco-0', CHUNK_CISCO)], normalize_query_terms(question), {}, max_claims=2)

    assert claims
    for claim in claims:
        for proibido in ('tema/cisco', 'tags', 'type:', '[!', '[[', '---'):
            assert proibido not in claim.text


def test_claims_do_chunk_com_stub_nao_viram_marcador_de_callout() -> None:
    question = 'o que é VLAN?'

    claims = _build_corpus_claims(question, [_hit('vlan-0', CHUNK_VLAN)], normalize_query_terms(question), {}, max_claims=2)

    assert claims
    for claim in claims:
        for proibido in ('[!note]', '[!', '[[', 'tags', 'tema/conceitos', '---'):
            assert proibido not in claim.text


def test_snippet_da_citacao_sai_sem_frontmatter_e_mantem_offsets() -> None:
    citation = _citation_from_corpus_hit(_hit('cisco-0', CHUNK_CISCO), {})

    assert citation.snippet == (
        '**Cisco — Trilha de Cursos e Certificações** Este arquivo centraliza os cursos em switches e VLAN.'
    )
    assert (citation.char_start, citation.char_end) == (0, len(CHUNK_CISCO))


def test_titulo_com_frontmatter_sem_h1_usa_nome_do_arquivo(tmp_path: Path) -> None:
    source = tmp_path / 'Trilha Cisco.md'
    source.write_text(CHUNK_CISCO, encoding='utf-8')

    note = structure_document(load_document(source))

    assert note.title == 'Trilha Cisco'


def test_titulo_com_frontmatter_usa_o_primeiro_h1(tmp_path: Path) -> None:
    source = tmp_path / 'vlan.md'
    source.write_text(CHUNK_VLAN, encoding='utf-8')

    note = structure_document(load_document(source))

    assert note.title == 'VLAN'


def test_titulo_nunca_vira_chave_yaml_solta(tmp_path: Path) -> None:
    source = tmp_path / 'sem-cabecalho.md'
    source.write_text('tags:\n\nUm texto explicativo suficientemente longo para ser resumo aqui.\n', encoding='utf-8')

    note = structure_document(load_document(source))

    assert 'tags' not in note.title
