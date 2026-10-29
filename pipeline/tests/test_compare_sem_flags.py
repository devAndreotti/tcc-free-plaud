"""Regressão: sem as flags novas, `benchmark compare` emite o mesmo JSON de antes.

O golden foi gerado pelo código anterior às flags. Campos que mudam a cada execução (ids, datas,
latências) viram `<volatil>` antes da comparação; o resto tem de bater byte a byte no conteúdo.
"""

import json
from pathlib import Path

from benchmark_compare_fakes import (
    ARGUMENTOS_BASE,
    FakeEmbedder,
    criar_suite,
    mascarar,
    settings_para,
)
from typer.testing import CliRunner

from escolio.benchmark.runner_models import BenchmarkComparisonResult
from escolio.cli import app

runner = CliRunner()
GOLDEN = Path(__file__).parent / 'fixtures' / 'compare_sem_flags_golden.json'


def executar_compare(tmp_path: Path, monkeypatch, argumentos: list[str]):
    settings = settings_para(tmp_path)
    suite_path = criar_suite(tmp_path)
    monkeypatch.setattr('escolio.benchmark.cli.get_settings', lambda: settings)
    monkeypatch.setattr('escolio.benchmark.cli.get_embedder', lambda model_name, **kwargs: FakeEmbedder())
    resultado = runner.invoke(app, ['benchmark', 'compare', '--suite', str(suite_path), *ARGUMENTOS_BASE, *argumentos])
    assert resultado.exit_code == 0, resultado.output
    return json.loads(resultado.stdout), settings


def test_sem_flags_o_json_bate_com_o_golden_de_antes(monkeypatch, tmp_path: Path) -> None:
    payload, _ = executar_compare(tmp_path, monkeypatch, [])
    real = mascarar(payload)
    esperado = json.loads(GOLDEN.read_text(encoding='utf-8'))
    if real != esperado:
        # Diagnostico: o diretorio coverage/ e enviado como artefato do CI (if: always()).
        saida = Path(__file__).resolve().parents[2] / 'coverage' / 'golden_compare_actual.json'
        saida.parent.mkdir(parents=True, exist_ok=True)
        saida.write_text(json.dumps(real, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')

    assert real == esperado


def test_sem_flags_so_existem_as_chaves_do_modelo(monkeypatch, tmp_path: Path) -> None:
    payload, _ = executar_compare(tmp_path, monkeypatch, [])

    assert set(payload) == set(BenchmarkComparisonResult.model_fields)
    for chave in ('reranked', 'baseline_ci', 'coverage', 'faithfulness'):
        assert chave not in payload


def test_sem_flags_o_arquivo_exportado_tem_so_as_chaves_do_modelo(monkeypatch, tmp_path: Path) -> None:
    payload, settings = executar_compare(tmp_path, monkeypatch, ['--export'])

    exportado = json.loads(Path(payload['json_report_path']).read_text(encoding='utf-8'))
    assert set(exportado) == set(BenchmarkComparisonResult.model_fields)
    assert exportado['comparison_id'] == payload['comparison_id']
    assert Path(payload['json_report_path']).parent == settings.results_dir
