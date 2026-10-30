"""Blocos do JSON do compare (IC do MRR, faithfulness, estratégia do chat) e mesclagem atômica. Sem rede."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from escolio.benchmark import json_merge
from escolio.benchmark.compare_blocks import (
    bloco_faithfulness,
    estrategia_de_referencia,
    intervalos_mrr,
)
from escolio.benchmark.coverage import parse_ks
from escolio.benchmark.faithfulness import FaithfulnessReport, StrategyFaithfulness
from escolio.benchmark.json_merge import mesclar_chaves_json
from escolio.benchmark.metrics import bootstrap_ci
from escolio.benchmark.runner_models import (
    BenchmarkComparisonResult,
    BenchmarkCorpusResult,
    BenchmarkQueryResult,
    BenchmarkSettingsSnapshot,
)


def _linha(sample_id: str, rr: float, categoria: str | None) -> BenchmarkQueryResult:
    return BenchmarkQueryResult(
        sample_id=sample_id,
        question=f'pergunta {sample_id}',
        hit_at_k=1 if rr else 0,
        reciprocal_rank=rr,
        latency_ms=0,
        category=categoria,
    )


def _corpus(linhas: list[BenchmarkQueryResult]) -> BenchmarkCorpusResult:
    return BenchmarkCorpusResult(
        note_count=1,
        positive_count=sum(1 for linha in linhas if linha.category != 'negativa'),
        negative_count=sum(1 for linha in linhas if linha.category == 'negativa'),
        retrieval_depth=10,
        summaries={},
        queries={'hybrid': linhas},
    )


def _comparacao(snapshot: BenchmarkSettingsSnapshot | None) -> BenchmarkComparisonResult:
    agora = datetime(2026, 10, 25, 12, 0, tzinfo=UTC)
    return BenchmarkComparisonResult(
        comparison_id='cmp-teste',
        suite_name='suite',
        embedding_model='fake',
        top_k=3,
        chunk_size=800,
        overlap=120,
        settings_snapshot=snapshot,
        summaries={},
        cases=[],
        started_at=agora,
        finished_at=agora,
        duration_ms=0,
    )


def _snapshot(estrategia: str) -> BenchmarkSettingsSnapshot:
    return BenchmarkSettingsSnapshot(
        embedding_model='fake',
        embedding_device='cpu',
        default_ask_strategy=estrategia,
        retrieval_top_k=3,
        default_chunk_size=800,
        default_chunk_overlap=120,
        answer_provider='extractive',
    )


def test_intervalo_do_mrr_usa_so_as_positivas_e_o_bootstrap_do_projeto() -> None:
    corpus = _corpus([_linha('a', 1.0, 'direta'), _linha('b', 0.5, 'inferida'), _linha('neg', 0.0, 'negativa')])

    intervalos = intervalos_mrr(corpus)

    esperado = bootstrap_ci([1.0, 0.5])  # a negativa (rr 0) não entra
    assert intervalos == {'hybrid': {'mrr_lower': esperado['lower'], 'mrr_upper': esperado['upper']}}


def test_intervalo_do_mrr_tem_so_as_chaves_que_a_ui_le() -> None:
    intervalos = intervalos_mrr(_corpus([_linha('a', 0.25, 'direta'), _linha('b', 1.0, 'direta')]))

    assert set(intervalos['hybrid']) == {'mrr_lower', 'mrr_upper'}
    assert intervalos['hybrid']['mrr_lower'] <= intervalos['hybrid']['mrr_upper']


def test_estrategia_de_referencia_segue_o_chat_e_cai_em_hybrid_sem_snapshot() -> None:
    assert estrategia_de_referencia(_comparacao(_snapshot('vector'))) == 'vector'
    assert estrategia_de_referencia(_comparacao(None)) == 'hybrid'


def test_bloco_faithfulness_traduz_a_estrategia_para_as_chaves_da_ui() -> None:
    relatorio = FaithfulnessReport(
        source_comparison_id='cmp-teste',
        suite_name='suite',
        judge_model='juiz-x',
        judge_base_url='http://juiz.local/v1',
        strategies={
            'hybrid': StrategyFaithfulness(
                strategy='hybrid',
                answer_count=2,
                claim_count=4,
                supported_count=3,
                unparsed_count=1,
                faithfulness={'mean': 0.75, 'lower': 0.5, 'upper': 1.0, 'confidence': 0.95},
                answers=[],
            )
        },
    )

    bloco = bloco_faithfulness(relatorio, 'hybrid')

    assert bloco == {
        'score': 0.75,
        'ci_lower': 0.5,
        'ci_upper': 1.0,
        'claims': 4,
        'unparsed': 1,
        'judge_model': 'juiz-x',
    }


def test_bloco_faithfulness_recusa_estrategia_ausente_e_sem_respostas() -> None:
    vazio = StrategyFaithfulness(
        strategy='lexical', answer_count=0, claim_count=0, supported_count=0, unparsed_count=0, faithfulness=None, answers=[]
    )
    relatorio = FaithfulnessReport(
        source_comparison_id='cmp-teste', suite_name='suite', judge_model='j', judge_base_url='u', strategies={'lexical': vazio}
    )

    with pytest.raises(ValueError, match='não está no relatório'):
        bloco_faithfulness(relatorio, 'vector')
    with pytest.raises(ValueError, match='não há respostas'):
        bloco_faithfulness(relatorio, 'lexical')


def test_parse_ks_ordena_sem_repetir_e_recusa_valores_invalidos() -> None:
    assert parse_ks('10,3,5,3') == [3, 5, 10]
    with pytest.raises(ValueError, match='inteiros'):
        parse_ks('3,x')
    with pytest.raises(ValueError, match='1 ou mais'):
        parse_ks('0')


def test_mesclagem_preserva_as_outras_chaves_e_nao_deixa_temporario(tmp_path: Path) -> None:
    alvo = tmp_path / 'compare.json'
    alvo.write_text(json.dumps({'comparison_id': 'cmp-1', 'summaries': {'hybrid': {'mrr': 0.5}}}), encoding='utf-8')

    mesclar_chaves_json(alvo, {'faithfulness': {'score': 0.9}}, comparison_id='cmp-1')

    assert json.loads(alvo.read_text(encoding='utf-8')) == {
        'comparison_id': 'cmp-1',
        'summaries': {'hybrid': {'mrr': 0.5}},
        'faithfulness': {'score': 0.9},
    }
    assert sorted(entrada.name for entrada in tmp_path.iterdir()) == ['compare.json']


def test_mesclagem_recusa_outra_comparacao_sem_tocar_no_arquivo(tmp_path: Path) -> None:
    alvo = tmp_path / 'compare.json'
    alvo.write_text(json.dumps({'comparison_id': 'cmp-1'}), encoding='utf-8')
    original = alvo.read_bytes()

    with pytest.raises(ValueError, match='não de'):
        mesclar_chaves_json(alvo, {'faithfulness': {}}, comparison_id='cmp-2')

    assert alvo.read_bytes() == original


@pytest.mark.parametrize('conteudo', ['não é json', '[1, 2]'])
def test_mesclagem_recusa_arquivo_que_nao_e_objeto_json(tmp_path: Path, conteudo: str) -> None:
    alvo = tmp_path / 'compare.json'
    alvo.write_text(conteudo, encoding='utf-8')

    with pytest.raises(ValueError):
        mesclar_chaves_json(alvo, {'faithfulness': {}})

    assert alvo.read_text(encoding='utf-8') == conteudo


def test_falha_na_troca_deixa_o_original_intacto_e_remove_o_temporario(tmp_path: Path, monkeypatch) -> None:
    alvo = tmp_path / 'compare.json'
    alvo.write_text(json.dumps({'comparison_id': 'cmp-1'}), encoding='utf-8')
    original = alvo.read_bytes()

    def falha(*args, **kwargs):
        raise OSError('disco cheio (simulado)')

    monkeypatch.setattr(json_merge.os, 'replace', falha)

    with pytest.raises(OSError, match='disco cheio'):
        mesclar_chaves_json(alvo, {'faithfulness': {}})

    assert alvo.read_bytes() == original
    assert sorted(entrada.name for entrada in tmp_path.iterdir()) == ['compare.json']
