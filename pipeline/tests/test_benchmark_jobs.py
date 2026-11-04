import json
import threading
import time

import pytest

from escolio.app.config import Settings
from escolio.benchmark.history import (
    list_benchmark_runs,
    load_benchmark_run,
    preview_benchmark_suite,
)
from escolio.benchmark.jobs import BenchmarkJobs, expected_steps


def _aguarda(jobs: BenchmarkJobs, status: str) -> dict:
    limite = time.monotonic() + 5
    while time.monotonic() < limite:
        estado = jobs.snapshot()
        if estado and estado['status'] == status:
            return estado
        time.sleep(0.01)
    raise AssertionError(f'não chegou em {status}: {jobs.snapshot()}')


def test_job_conta_os_passos_e_entrega_o_resultado():
    def rodar(on_progress):
        on_progress({'phase': 'notas', 'strategy': 'lexical', 'note': 'A'})
        on_progress({'phase': 'corpus', 'strategy': 'hybrid', 'question': 'Q?', 'negative': True, 'answered': False})
        return {'comparison_id': 'cmp-1'}

    jobs = BenchmarkJobs()
    jobs.start(suite_name='s', total=2, answer=False, run=rodar)
    estado = _aguarda(jobs, 'done')
    assert estado['done'] == 2
    assert estado['result'] == {'comparison_id': 'cmp-1'}
    assert estado['recent'] == [{'question': 'Q?', 'strategy': 'hybrid', 'negative': True, 'answered': False}]


def test_cancelar_para_na_proxima_pergunta():
    pode_seguir = threading.Event()
    passos: list[int] = []

    def rodar(on_progress):
        on_progress({'phase': 'corpus', 'strategy': 'lexical', 'question': '1'})
        passos.append(1)
        pode_seguir.wait(5)
        on_progress({'phase': 'corpus', 'strategy': 'lexical', 'question': '2'})
        passos.append(2)
        return {}

    jobs = BenchmarkJobs()
    jobs.start(suite_name='s', total=2, answer=False, run=rodar)
    while not passos:
        time.sleep(0.01)
    assert jobs.cancel()['status'] == 'running'
    pode_seguir.set()
    estado = _aguarda(jobs, 'cancelled')
    assert passos == [1]
    assert estado['result'] is None


def test_falha_chega_a_tela():
    def rodar(_on_progress):
        raise ValueError('suite ruim')

    jobs = BenchmarkJobs()
    jobs.start(suite_name='s', total=1, answer=False, run=rodar)
    assert _aguarda(jobs, 'error')['error'] == 'suite ruim'


def test_nao_inicia_duas_comparacoes_ao_mesmo_tempo():
    libera = threading.Event()
    chamadas: list[int] = []

    def rodar(_on_progress):
        chamadas.append(1)
        libera.wait(5)
        return {}

    jobs = BenchmarkJobs()
    jobs.start(suite_name='a', total=1, answer=False, run=rodar)
    segunda = jobs.start(suite_name='b', total=1, answer=False, run=rodar)
    assert segunda['suite_name'] == 'a'
    libera.set()
    _aguarda(jobs, 'done')
    assert chamadas == [1]


def test_passos_esperados_contam_notas_e_perguntas():
    previa = {'note_count': 10, 'positive_count': 37, 'negative_count': 39}
    assert expected_steps(previa) == (10 + 76) * 3
    assert expected_steps(previa, passes=2) == (10 + 76) * 6


def _settings(tmp_path) -> Settings:
    return Settings(workspace_dir=tmp_path, results_dir=tmp_path / 'results')


def test_previa_le_a_suite_sem_indexar(tmp_path):
    (tmp_path / 'd.json').write_text(json.dumps([
        {'sample_id': 'a', 'question': 'Com resposta?', 'expected_note_id': 'n', 'expected_ref': 'Seção 1'},
    ]), encoding='utf-8')
    (tmp_path / 'neg.json').write_text(json.dumps([
        {'sample_id': 'b', 'question': 'Sem resposta?', 'category': 'negativa'},
    ]), encoding='utf-8')
    (tmp_path / 'suite.json').write_text(json.dumps({
        'suite_name': 'minha',
        'cases': [{'case_id': 'c', 'document_path': 'nota.md', 'dataset_path': 'd.json'}],
        'negative_dataset_path': 'neg.json',
    }), encoding='utf-8')
    previa = preview_benchmark_suite('suite.json', settings=_settings(tmp_path))
    assert (previa['suite_name'], previa['note_count'], previa['positive_count'], previa['negative_count']) == (
        'minha', 1, 1, 1,
    )
    assert previa['questions'][0] == {
        'question': 'Com resposta?', 'note': 'nota', 'expected_ref': 'Seção 1', 'negative': False,
    }
    assert previa['questions'][1]['negative'] is True


def _grava_rodada(pasta, id_rodada: str, **extra) -> None:
    pasta.mkdir(exist_ok=True)
    conteudo = {'comparison_id': id_rodada, 'suite_name': 's', **extra}
    (pasta / f'{id_rodada}.json').write_text(json.dumps(conteudo), encoding='utf-8')


def test_historico_le_as_metricas_da_hibrida_e_ignora_lixo(tmp_path):
    settings = _settings(tmp_path)
    resumo = {
        'mrr': 0.811,
        'recall_at_3': 0.946,
        'abstention': {'accuracy': 0.513, 'recall': 0.5, 'answered_positive_rate': 0.5},
    }
    _grava_rodada(settings.results_dir, 'cmp-aaaaaaaaaaaa', corpus={
        'positive_count': 37,
        'negative_count': 39,
        'summaries': {'hybrid': resumo},
    })
    (settings.results_dir / 'cmp-bbbbbbbbbbbb.json').write_text('{quebrado', encoding='utf-8')
    (settings.results_dir / 'cmp-naoehid.json').write_text('{}', encoding='utf-8')
    linhas = list_benchmark_runs(settings=settings)
    assert [linha['comparison_id'] for linha in linhas] == ['cmp-aaaaaaaaaaaa']
    assert linhas[0]['mrr'] == 0.811
    assert linhas[0]['accuracy'] == 0.513
    assert linhas[0]['answer_provider'] == 'extractive'


def test_carregar_rodada_recusa_id_que_vira_caminho(tmp_path):
    settings = _settings(tmp_path)
    _grava_rodada(settings.results_dir, 'cmp-aaaaaaaaaaaa')
    assert load_benchmark_run('cmp-aaaaaaaaaaaa', settings=settings)['ok'] is True
    for invalido in ('../segredo', 'cmp-aaaaaaaaaaaa/../x', 'cmp-zzzzzzzzzzzz', ''):
        with pytest.raises(ValueError):
            load_benchmark_run(invalido, settings=settings)
