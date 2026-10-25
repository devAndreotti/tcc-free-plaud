"""`benchmark faithfulness --mesclar-em`: grava a chave faithfulness no JSON do compare. Juiz falso, sem rede."""

import json
from pathlib import Path

import pytest
from benchmark_compare_fakes import (
    ARGUMENTOS_BASE,
    FakeEmbedder,
    criar_suite,
    settings_para,
)
from typer.testing import CliRunner

from escolio.cli import app

runner = CliRunner()
CHAVES_FAITHFULNESS = {'score', 'ci_lower', 'ci_upper', 'claims', 'unparsed', 'judge_model'}


class JuizFalso:
    """Marca toda afirmação como suportada e registra quantas chamadas recebeu."""

    def __init__(self) -> None:
        self.chamadas = 0

    def __call__(self, prompt: str) -> str:
        self.chamadas += 1
        return 'SUPORTADO'


@pytest.fixture()
def comparacao(monkeypatch, tmp_path: Path) -> Path:
    """Compare com --registrar-respostas e --export: respostas extrativas com trechos citados."""
    settings = settings_para(tmp_path)
    suite_path = criar_suite(tmp_path)
    monkeypatch.setattr('escolio.benchmark.cli.get_settings', lambda: settings)
    monkeypatch.setattr('escolio.benchmark.cli.get_embedder', lambda model_name, **kwargs: FakeEmbedder())
    resultado = runner.invoke(
        app,
        ['benchmark', 'compare', '--suite', str(suite_path), *ARGUMENTOS_BASE, '--registrar-respostas', '--export'],
    )
    assert resultado.exit_code == 0, resultado.output
    return Path(json.loads(resultado.stdout)['json_report_path'])


def _faithfulness(monkeypatch, juiz: JuizFalso) -> None:
    monkeypatch.setattr(
        'escolio.benchmark.cli.make_openai_compatible_judge',
        lambda base_url, model, api_key=None, timeout=120: juiz,
    )


def _julgar(caminho: Path, saida: Path, *extras: str):
    return runner.invoke(
        app,
        [
            'benchmark', 'faithfulness',
            '--results', str(caminho),
            '--judge-model', 'juiz-x',
            '--judge-base-url', 'http://juiz.local/v1',
            '--saida', str(saida),
            *extras,
        ],
    )


def test_sem_mesclar_o_compare_fica_byte_a_byte_igual(monkeypatch, tmp_path: Path, comparacao: Path) -> None:
    original = comparacao.read_bytes()
    _faithfulness(monkeypatch, JuizFalso())

    resultado = _julgar(comparacao, tmp_path / 'faith.json')

    assert resultado.exit_code == 0, resultado.output
    assert comparacao.read_bytes() == original
    assert 'mesclado_em' not in json.loads(resultado.stdout)


def test_mesclar_grava_a_faithfulness_da_estrategia_do_chat_e_preserva_o_resto(
    monkeypatch, tmp_path: Path, comparacao: Path
) -> None:
    antes = json.loads(comparacao.read_text(encoding='utf-8'))
    juiz = JuizFalso()
    _faithfulness(monkeypatch, juiz)
    saida = tmp_path / 'faith.json'

    resultado = _julgar(comparacao, saida, '--mesclar-em', str(comparacao))

    assert resultado.exit_code == 0, resultado.output
    assert juiz.chamadas > 0
    depois = json.loads(comparacao.read_text(encoding='utf-8'))
    assert set(depois) == set(antes) | {'faithfulness'}
    assert {chave: depois[chave] for chave in antes} == antes  # nada do que já existia mudou
    bloco = depois['faithfulness']
    assert set(bloco) == CHAVES_FAITHFULNESS
    assert bloco['judge_model'] == 'juiz-x'
    assert bloco['score'] == 1.0  # juiz que aprova tudo
    assert bloco['ci_lower'] <= bloco['score'] <= bloco['ci_upper']
    assert bloco['claims'] > 0 and bloco['unparsed'] == 0

    relatorio = json.loads(saida.read_text(encoding='utf-8'))
    assert bloco == {
        'score': relatorio['strategies']['hybrid']['faithfulness']['mean'],
        'ci_lower': relatorio['strategies']['hybrid']['faithfulness']['lower'],
        'ci_upper': relatorio['strategies']['hybrid']['faithfulness']['upper'],
        'claims': relatorio['strategies']['hybrid']['claim_count'],
        'unparsed': relatorio['strategies']['hybrid']['unparsed_count'],
        'judge_model': 'juiz-x',
    }
    assert json.loads(resultado.stdout)['mesclado_em'] == str(comparacao)


def test_estrategia_explicita_escolhe_o_bloco(monkeypatch, tmp_path: Path, comparacao: Path) -> None:
    _faithfulness(monkeypatch, JuizFalso())
    saida = tmp_path / 'faith.json'

    resultado = _julgar(comparacao, saida, '--mesclar-em', str(comparacao), '--estrategia', 'lexical')

    assert resultado.exit_code == 0, resultado.output
    relatorio = json.loads(saida.read_text(encoding='utf-8'))
    bloco = json.loads(comparacao.read_text(encoding='utf-8'))['faithfulness']
    assert bloco['claims'] == relatorio['strategies']['lexical']['claim_count']
    assert bloco['score'] == relatorio['strategies']['lexical']['faithfulness']['mean']


def test_estrategia_desconhecida_falha_sem_tocar_nos_arquivos(monkeypatch, tmp_path: Path, comparacao: Path) -> None:
    original = comparacao.read_bytes()
    _faithfulness(monkeypatch, JuizFalso())
    saida = tmp_path / 'faith.json'

    resultado = _julgar(comparacao, saida, '--mesclar-em', str(comparacao), '--estrategia', 'semantica')

    assert resultado.exit_code == 1
    assert 'não está no relatório' in resultado.output
    assert comparacao.read_bytes() == original
    assert not saida.exists()


def test_mesclar_recusa_compare_de_outra_comparacao(monkeypatch, tmp_path: Path, comparacao: Path) -> None:
    outra = tmp_path / 'outra.json'
    dados = json.loads(comparacao.read_text(encoding='utf-8'))
    dados['comparison_id'] = 'cmp-outra'
    outra.write_text(json.dumps(dados), encoding='utf-8')
    original = outra.read_bytes()
    _faithfulness(monkeypatch, JuizFalso())

    resultado = _julgar(comparacao, tmp_path / 'faith.json', '--mesclar-em', str(outra))

    assert resultado.exit_code == 1
    assert 'não vou gravar' in resultado.output
    assert outra.read_bytes() == original
    assert sorted(entrada.name for entrada in tmp_path.iterdir() if entrada.name.startswith('.')) == []
