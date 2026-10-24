import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from escolio.benchmark.cli import app
from escolio.benchmark.coverage import (
    build_coverage_row,
    coverage_summary,
    grupo_da_pergunta,
    joined_hit_at_k,
    normalizar_texto,
    term_coverage_at_k,
    trechos_do_ranking,
)
from escolio.benchmark.metrics import bootstrap_ci
from escolio.benchmark.runners import _contains_expected_terms
from escolio.ingest.loaders import load_document
from escolio.notes.structurer import structure_document
from escolio.retrieval.indexer import index_note

REPO_ROOT = Path(__file__).resolve().parents[2]
DATASET_DIR = REPO_ROOT / 'data' / 'datasets' / 'multi_trecho_cobertura'
SUITE_PATH = DATASET_DIR / 'suite.json'
NOTAS_DIR = REPO_ROOT / 'data' / 'datasets' / 'multi_trecho' / 'notas'


# --- cobertura, k e junção -------------------------------------------------------------------------


def test_cobertura_zero_parcial_e_total() -> None:
    chunks = ['alpha beta', 'gamma']
    assert term_coverage_at_k(['delta', 'epsilon'], chunks, k=2) == 0.0
    assert term_coverage_at_k(['alpha', 'delta'], chunks, k=2) == 0.5
    assert term_coverage_at_k(['alpha', 'gamma'], chunks, k=2) == 1.0


def test_k_considera_so_os_primeiros_trechos_do_ranking() -> None:
    chunks = ['x', 'alpha', 'beta']
    assert term_coverage_at_k(['alpha', 'beta'], chunks, k=1) == 0.0
    assert term_coverage_at_k(['alpha', 'beta'], chunks, k=2) == 0.5
    assert term_coverage_at_k(['alpha', 'beta'], chunks, k=3) == 1.0
    assert joined_hit_at_k(['alpha', 'beta'], chunks, k=2) == 0
    assert joined_hit_at_k(['alpha', 'beta'], chunks, k=3) == 1


def test_junta_termos_de_chunks_diferentes_sem_chunk_isolado_completo() -> None:
    chunks = ['a replication factor 3 aparece aqui', 'e a data do cutover foi 22/03/2025 ali']
    termos = ['replication factor 3', '22/03/2025']
    # O scorer atual exige todos os termos num chunk; a cobertura soma a união do top-k.
    assert not any(_contains_expected_terms(texto, termos) for texto in chunks)
    assert term_coverage_at_k(termos, chunks, k=2) == 1.0
    assert joined_hit_at_k(termos, chunks, k=2) == 1


def test_acentos_caixa_e_espacos_nao_mudam_o_resultado() -> None:
    chunks = ['Três ACKs duplicados, ação\nrápida: não é isso']
    assert term_coverage_at_k(['três acks duplicados'], chunks, k=1) == 1.0
    assert term_coverage_at_k(['TRES ACKS duplicados'], chunks, k=1) == 1.0
    assert term_coverage_at_k(['acao rapida'], chunks, k=1) == 1.0
    assert term_coverage_at_k(['replicacao'], chunks, k=1) == 0.0
    assert normalizar_texto('  Ação   Ótima\n') == 'acao otima'


@pytest.mark.parametrize(
    ('chamada', 'excecao'),
    [
        (lambda: term_coverage_at_k([], ['x'], k=1), ValueError),
        (lambda: term_coverage_at_k(['x'], ['x'], k=0), ValueError),
        (lambda: joined_hit_at_k(['  '], ['x'], k=1), ValueError),
    ],
)
def test_entradas_invalidas_levantam_erro(chamada, excecao) -> None:
    with pytest.raises(excecao):
        chamada()


def test_lista_vazia_de_trechos_da_cobertura_zero() -> None:
    assert term_coverage_at_k(['alpha'], [], k=3) == 0.0


# --- grupos ----------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ('sample_id', 'grupo'),
    [
        ('unica-01', 'unica'),
        ('mt-nota-01', 'mt-nota'),
        ('mt-notas-01', 'mt-notas'),
        ('mtneg-01', 'outro'),
    ],
)
def test_grupo_pelo_prefixo_do_sample_id(sample_id: str, grupo: str) -> None:
    assert grupo_da_pergunta(sample_id) == grupo


# --- reconstrução do texto pelos offsets -----------------------------------------------------------


def test_trechos_do_ranking_seguem_a_ordem_do_rank_e_os_offsets() -> None:
    textos = {'nota-a': 'abcdefghij'}
    retrieved = [
        {'rank': 2, 'note_id': 'nota-a', 'char_start': 5, 'char_end': 10},
        {'rank': 1, 'note_id': 'nota-a', 'char_start': 0, 'char_end': 5},
    ]
    assert trechos_do_ranking(retrieved, textos) == ['abcde', 'fghij']


def test_trechos_do_ranking_falha_com_nota_ausente_ou_offset_invalido() -> None:
    textos = {'nota-a': 'abcdefghij'}
    with pytest.raises(ValueError, match='não está na suite'):
        trechos_do_ranking([{'rank': 1, 'note_id': 'outra', 'char_start': 0, 'char_end': 2}], textos)
    with pytest.raises(ValueError, match='fora do texto'):
        trechos_do_ranking([{'rank': 1, 'note_id': 'nota-a', 'char_start': 0, 'char_end': 99}], textos)


# --- IC bootstrap e resumo por grupo ----------------------------------------------------------------


def test_bootstrap_ci_valores_constantes_e_unico() -> None:
    constante = bootstrap_ci([1.0, 1.0, 1.0])
    assert constante['mean'] == constante['lower'] == constante['upper'] == 1.0
    unico = bootstrap_ci([0.5])
    assert unico['mean'] == unico['lower'] == unico['upper'] == 0.5


def test_bootstrap_ci_contem_a_media_e_e_deterministico() -> None:
    valores = [0.0, 1.0, 0.0, 1.0, 1.0, 0.5]
    primeiro = bootstrap_ci(valores)
    assert primeiro['lower'] <= primeiro['mean'] <= primeiro['upper']
    assert primeiro == bootstrap_ci(valores)


def test_resumo_separa_grupos_e_agrega_todos() -> None:
    ks = [1, 2]
    rows = [
        build_coverage_row('lexical', 'mt-nota-01', ['a', 'b'], ['a', 'b'], ks),
        build_coverage_row('lexical', 'mt-nota-02', ['a', 'b'], ['a', 'x'], ks),
        build_coverage_row('lexical', 'mt-notas-01', ['c'], ['x'], ks),
        build_coverage_row('vector', 'mt-nota-01', ['a'], ['a'], ks),
    ]
    cells = {(c['strategy'], c['grupo'], c['k']): c for c in coverage_summary(rows)}

    celula = cells[('lexical', 'mt-nota', 2)]
    assert celula['n'] == 2
    assert celula['cobertura']['mean'] == pytest.approx(0.75)
    assert celula['juncao_completa']['mean'] == pytest.approx(0.5)
    assert cells[('lexical', 'todos', 2)]['n'] == 3
    assert cells[('lexical', 'mt-notas', 1)]['cobertura']['mean'] == 0.0
    assert ('vector', 'todos', 2) in cells


# --- subcomando CLI ---------------------------------------------------------------------------------


def _chunks(note_id: str) -> list[str]:
    note = structure_document(load_document(NOTAS_DIR / f'{note_id}.md'))
    return [chunk.chunk_text for chunk in index_note(note, chunk_size=800, overlap=120)]


def _hit(rank: int, note_id: str, contem: str, *, avoid: str | None = None) -> dict:
    """Hit no formato do compare: offsets do primeiro chunk que contém `contem` e não contém `avoid`."""
    note = structure_document(load_document(NOTAS_DIR / f'{note_id}.md'))
    chunks = index_note(note, chunk_size=800, overlap=120)
    alvo = next(
        c
        for c in chunks
        if contem.lower() in c.chunk_text.lower() and (avoid is None or avoid.lower() not in c.chunk_text.lower())
    )
    return {'rank': rank, 'note_id': note_id, 'char_start': alvo.char_start, 'char_end': alvo.char_end}


def _compare_fixture(path: Path) -> Path:
    # mt-nota-01: 'replication factor 3' e 'dia 20' em chunks distintos, ambos no top-2.
    mt_nota_01 = [
        _hit(1, 'ata-migracao-kafka', 'replication factor 3'),
        _hit(2, 'ata-migracao-kafka', 'dia 20', avoid='replication factor 3'),
    ]
    # mt-nota-02: só 'acks=all' no top-2; a data 22/03/2025 não aparece.
    mt_nota_02 = [
        _hit(1, 'ata-migracao-kafka', 'acks=all'),
        _hit(2, 'ata-migracao-kafka', 'pedido', avoid='22/03/2025'),
    ]
    # mt-notas-01: 12 partições (Kafka) e salting (Parquet) no top-2.
    mt_notas_01 = [
        _hit(1, 'ata-migracao-kafka', '12 partições'),
        _hit(2, 'aula-particionamento-parquet', 'salting'),
    ]
    # Negativa: não pertence à suite de pontuação e deve ser ignorada.
    negativa = [_hit(1, 'ata-migracao-kafka', 'pedido')]
    payload = {
        'comparison_id': 'cmp-teste',
        'suite_name': 'multi-trecho-cobertura-suite',
        'corpus': {
            'retrieval_depth': 10,
            'queries': {
                'lexical': [
                    {'sample_id': 'mt-nota-01', 'retrieved': mt_nota_01},
                    {'sample_id': 'mt-nota-02', 'retrieved': mt_nota_02},
                    {'sample_id': 'mtneg-01', 'retrieved': negativa},
                ],
                'vector': [{'sample_id': 'mt-notas-01', 'retrieved': mt_notas_01}],
            },
        },
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
    return path


def test_cli_coverage_gera_celulas_com_textos_reconstruidos(tmp_path: Path) -> None:
    resultado = _compare_fixture(tmp_path / 'compare.json')
    saida = tmp_path / 'cobertura.json'
    runner = CliRunner()
    invocacao = runner.invoke(
        app,
        [
            'coverage',
            '--results', str(resultado),
            '--suite', str(SUITE_PATH),
            '--k', '1,2',
            '--saida', str(saida),
            '--workspace', str(REPO_ROOT),
        ],
    )
    assert invocacao.exit_code == 0, invocacao.output
    payload = json.loads(saida.read_text(encoding='utf-8'))
    assert payload['ks'] == [1, 2]
    assert payload['perguntas_pontuadas'] == 3  # a negativa fica de fora

    cells = {(c['strategy'], c['grupo'], c['k']): c for c in payload['celulas']}
    lexical_mt_nota_k2 = cells[('lexical', 'mt-nota', 2)]
    assert lexical_mt_nota_k2['n'] == 2
    assert lexical_mt_nota_k2['cobertura']['mean'] == pytest.approx(0.75)
    assert lexical_mt_nota_k2['juncao_completa']['mean'] == pytest.approx(0.5)
    assert cells[('vector', 'mt-notas', 2)]['juncao_completa']['mean'] == 1.0
    assert cells[('vector', 'mt-notas', 1)]['cobertura']['mean'] == pytest.approx(0.5)


def test_cli_coverage_recusa_k_acima_da_profundidade_gravada(tmp_path: Path) -> None:
    resultado = _compare_fixture(tmp_path / 'compare.json')
    invocacao = CliRunner().invoke(
        app,
        [
            'coverage',
            '--results', str(resultado),
            '--suite', str(SUITE_PATH),
            '--k', '3,11',
            '--saida', str(tmp_path / 'x.json'),
            '--workspace', str(REPO_ROOT),
        ],
    )
    assert invocacao.exit_code == 1
    assert 'profundidade' in invocacao.output


def test_cli_coverage_recusa_json_sem_passada_no_corpus(tmp_path: Path) -> None:
    sem_corpus = tmp_path / 'sem_corpus.json'
    sem_corpus.write_text(json.dumps({'comparison_id': 'x', 'corpus': None}), encoding='utf-8')
    invocacao = CliRunner().invoke(
        app,
        [
            'coverage',
            '--results', str(sem_corpus),
            '--suite', str(SUITE_PATH),
            '--saida', str(tmp_path / 'x.json'),
            '--workspace', str(REPO_ROOT),
        ],
    )
    assert invocacao.exit_code == 1
    assert 'corpus.queries' in invocacao.output
