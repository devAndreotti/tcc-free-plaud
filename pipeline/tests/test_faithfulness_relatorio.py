"""Relatório, cliente HTTP do juiz e subcomando CLI da faithfulness (juiz falso, sem rede)."""

import json
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError

import pytest
from typer.testing import CliRunner

from escolio.benchmark.faithfulness import (
    build_faithfulness_report,
    make_openai_compatible_judge,
)
from escolio.benchmark.runners import (
    BenchmarkComparisonResult,
    BenchmarkCorpusResult,
    BenchmarkQueryResult,
    BenchmarkStrategySummary,
)
from escolio.cli import app
from escolio.providers.answer import AnswerProviderError

runner = CliRunner()


class JuizFalso:
    """Juiz determinístico: SUPORTADO quando a afirmação contém uma das palavras-chave."""

    def __init__(self, palavras: tuple[str, ...] = (), resposta_fixa: str | None = None) -> None:
        self.palavras = palavras
        self.resposta_fixa = resposta_fixa
        self.chamadas: list[str] = []

    def __call__(self, prompt: str) -> str:
        self.chamadas.append(prompt)
        if self.resposta_fixa is not None:
            return self.resposta_fixa
        afirmacao = prompt.split('AFIRMACAO:\n', 1)[1].split('\n\nVeredito', 1)[0].lower()
        return 'SUPORTADO' if any(palavra in afirmacao for palavra in self.palavras) else 'NAO_SUPORTADO'


def _linha(sample_id: str, *, answered: bool, answer: str | None = None, contexts: list[str] | None = None) -> BenchmarkQueryResult:
    return BenchmarkQueryResult(
        sample_id=sample_id,
        question=f'Pergunta {sample_id}?',
        hit_at_k=0,
        reciprocal_rank=0.0,
        latency_ms=0,
        answered=answered,
        answer=answer,
        contexts=contexts,
    )


def _comparacao(linhas: list[BenchmarkQueryResult]) -> BenchmarkComparisonResult:
    agora = datetime(2026, 10, 24, 12, 0, tzinfo=UTC)

    def resumo(estrategia: str) -> BenchmarkStrategySummary:
        return BenchmarkStrategySummary(
            strategy=estrategia,
            case_count=1,
            query_count=len(linhas),
            mrr=0.0,
            recall_at_3=0.0,
            recall_at_5=0.0,
            recall_at_10=0.0,
            ndcg_at_10=0.0,
            duration_ms=1,
            avg_query_latency_ms=1.0,
        )

    return BenchmarkComparisonResult(
        comparison_id='cmp-faith',
        suite_name='faith-suite',
        embedding_model='fake-hash',
        top_k=3,
        chunk_size=200,
        overlap=20,
        summaries={'hybrid': resumo('hybrid')},
        cases=[],
        corpus=BenchmarkCorpusResult(
            note_count=2,
            positive_count=2,
            negative_count=0,
            retrieval_depth=10,
            summaries={'hybrid': resumo('hybrid')},
            queries={'hybrid': linhas},
        ),
        started_at=agora,
        finished_at=agora,
        duration_ms=1,
    )


def _linhas_com_respostas() -> list[BenchmarkQueryResult]:
    return [
        _linha('q1', answered=True, answer='O Kafka é o broker [1]. O Redis expira [2].', contexts=['Kafka broker.', 'Redis timeout.']),
        _linha('q2', answered=True, answer='O Kafka é o broker.', contexts=['Kafka broker.']),
        _linha('q3', answered=False),
    ]


def test_relatorio_agrega_por_estrategia_com_bootstrap_e_pula_sem_resposta() -> None:
    juiz = JuizFalso(palavras=('kafka',))
    relatorio = build_faithfulness_report(_comparacao(_linhas_com_respostas()), juiz, judge_model='juiz-x', judge_base_url='http://j/v1')

    hybrid = relatorio.strategies['hybrid']
    assert (hybrid.answer_count, hybrid.claim_count, hybrid.supported_count, hybrid.unparsed_count) == (2, 3, 2, 0)
    assert [answer.score for answer in hybrid.answers] == [0.5, 1.0]
    assert len(juiz.chamadas) == 3  # uma chamada de juiz por afirmação; q3 (sem resposta) não é julgada
    assert hybrid.faithfulness is not None
    assert hybrid.faithfulness['mean'] == 0.75
    assert hybrid.faithfulness['lower'] <= hybrid.faithfulness['mean'] <= hybrid.faithfulness['upper']
    assert relatorio.judge_model == 'juiz-x' and relatorio.prompt_version == 'faithfulness-pt-v1'

    # bootstrap determinístico: mesma entrada, mesmo intervalo
    outro = build_faithfulness_report(_comparacao(_linhas_com_respostas()), JuizFalso(palavras=('kafka',)), judge_model='j', judge_base_url='u')
    assert outro.strategies['hybrid'].faithfulness == hybrid.faithfulness


def test_relatorio_sem_respostas_nao_inventa_intervalo() -> None:
    relatorio = build_faithfulness_report(
        _comparacao([_linha('q1', answered=False)]), JuizFalso(), judge_model='j', judge_base_url='u'
    )
    assert relatorio.strategies['hybrid'].answer_count == 0
    assert relatorio.strategies['hybrid'].faithfulness is None


def test_relatorio_recusa_json_sem_respostas_gravadas() -> None:
    comparacao = _comparacao([_linha('q1', answered=True, answer=None)])
    with pytest.raises(ValueError, match='registrar-respostas'):
        build_faithfulness_report(comparacao, JuizFalso(), judge_model='j', judge_base_url='u')

    sem_corpus = _comparacao([])
    sem_corpus.corpus = None
    with pytest.raises(ValueError, match='passada no corpus'):
        build_faithfulness_report(sem_corpus, JuizFalso(), judge_model='j', judge_base_url='u')


class _RespostaHttp:
    def __init__(self, corpo: bytes) -> None:
        self.corpo = corpo

    def __enter__(self):
        return self

    def __exit__(self, *args) -> None:
        return None

    def read(self) -> bytes:
        return self.corpo


def test_juiz_http_envia_temperatura_zero_e_le_o_conteudo(monkeypatch) -> None:
    capturado: dict = {}

    def urlopen_falso(request, timeout):
        capturado.update(url=request.full_url, headers=dict(request.headers), body=json.loads(request.data), timeout=timeout)
        return _RespostaHttp(json.dumps({'choices': [{'message': {'content': ' NAO_SUPORTADO '}, 'finish_reason': 'stop'}]}).encode())

    monkeypatch.setattr('escolio.benchmark.faithfulness.urlopen', urlopen_falso)
    juiz = make_openai_compatible_judge('http://localhost:11434/v1/', 'qwen-juiz', api_key='segredo', timeout=7)

    assert juiz('PROMPT') == 'NAO_SUPORTADO'
    assert capturado['url'] == 'http://localhost:11434/v1/chat/completions'
    assert capturado['body']['temperature'] == 0
    assert capturado['body']['messages'] == [{'role': 'user', 'content': 'PROMPT'}]
    assert capturado['headers']['Authorization'] == 'Bearer segredo'
    assert capturado['timeout'] == 7


def test_juiz_http_traduz_falhas_de_transporte(monkeypatch) -> None:
    def http_500(request, timeout):
        raise HTTPError(request.full_url, 500, 'erro', None, None)

    monkeypatch.setattr('escolio.benchmark.faithfulness.urlopen', http_500)
    with pytest.raises(AnswerProviderError, match='HTTP 500'):
        make_openai_compatible_judge('http://j/v1', 'm')('PROMPT')

    with pytest.raises(AnswerProviderError):
        make_openai_compatible_judge('ftp://j/v1', 'm')


def test_cli_faithfulness_grava_relatorio_com_juiz_falso(monkeypatch, tmp_path: Path) -> None:
    resultados = tmp_path / 'com-respostas.json'
    resultados.write_text(_comparacao(_linhas_com_respostas()).model_dump_json(), encoding='utf-8')
    saida = tmp_path / 'faithfulness' / 'hybrid.json'
    monkeypatch.setattr(
        'escolio.benchmark.cli.make_openai_compatible_judge',
        lambda *args, **kwargs: JuizFalso(palavras=('kafka',)),
    )

    result = runner.invoke(
        app,
        [
            'benchmark', 'faithfulness',
            '--results', str(resultados),
            '--judge-model', 'juiz-x',
            '--judge-base-url', 'http://localhost:11434/v1',
            '--saida', str(saida),
        ],
    )

    assert result.exit_code == 0, result.output
    relido = json.loads(saida.read_text(encoding='utf-8'))
    assert relido['judge_model'] == 'juiz-x'
    assert relido['strategies']['hybrid']['faithfulness']['mean'] == 0.75


def test_cli_faithfulness_recusa_json_sem_respostas(monkeypatch, tmp_path: Path) -> None:
    resultados = tmp_path / 'sem-respostas.json'
    resultados.write_text(_comparacao([_linha('q1', answered=True, answer=None)]).model_dump_json(), encoding='utf-8')
    monkeypatch.setattr('escolio.benchmark.cli.make_openai_compatible_judge', lambda *args, **kwargs: JuizFalso())

    result = runner.invoke(
        app,
        [
            'benchmark', 'faithfulness',
            '--results', str(resultados),
            '--judge-model', 'juiz-x',
            '--judge-base-url', 'http://localhost:11434/v1',
            '--saida', str(tmp_path / 'saida.json'),
        ],
    )

    assert result.exit_code == 1
    assert '--registrar-respostas' in result.output
    assert not (tmp_path / 'saida.json').exists()
