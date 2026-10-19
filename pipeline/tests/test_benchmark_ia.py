import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

from typer.testing import CliRunner

from escolio.app.config import Settings
from escolio.benchmark.answer_metrics import generation_discard_reason, limitation_code
from escolio.benchmark.datasets import load_benchmark_suite
from escolio.benchmark.runners import (
    BenchmarkAnswerMetrics,
    BenchmarkComparisonResult,
    BenchmarkCorpusResult,
    BenchmarkQueryResult,
    BenchmarkStrategySummary,
    _summarize_answer_metrics,
    compare_benchmark_suite,
)
from escolio.cli import app
from escolio.corpus.ask import validate_generated_answer
from escolio.providers.answer import NO_ANSWER_SENTINEL, OpenAICompatibleAnswerProvider
from escolio.retrieval.models import AskResponse
from escolio.storage.sqlite import init_sqlite
from escolio.storage.vector import LocalVectorStore

runner = CliRunner()
ESTRATEGIAS = ('lexical', 'vector', 'hybrid')


class FakeEmbedder:
    model_name = 'fake-hash'

    def embed(self, texts: list[str]) -> list[list[float]]:
        embeddings: list[list[float]] = []
        for text in texts:
            vector = [0.0] * 16
            for token in text.lower().split():
                slot = sum(ord(char) for char in token) % len(vector)
                vector[slot] += 1.0
            embeddings.append(vector)
        return embeddings


class FakeAnswerProvider:
    provider_name = 'fake'
    model = 'fake-qchat'

    def __init__(self, *, reply: str = '', error: Exception | None = None) -> None:
        self.reply = reply
        self.error = error

    def answer(self, question: str, contexts: list[str]) -> str:
        if self.error is not None:
            raise self.error
        return self.reply


def _suite_com_corpus(tmp_path: Path) -> Path:
    documents = {
        'kafka': '# Kafka\n\nO Apache Kafka foi adotado como broker padrao da plataforma de eventos.\n',
        'redis': '# Redis\n\nO timeout do Redis em staging esta configurado para trinta segundos.\n',
    }
    cases = []
    for name, text in documents.items():
        (tmp_path / f'{name}.md').write_text(text, encoding='utf-8')
        (tmp_path / f'{name}.json').write_text(
            json.dumps(
                {
                    'dataset_name': name,
                    'samples': [
                        {
                            'sample_id': f'{name}-1',
                            'question': f'Qual a configuracao do {name}?',
                            'expected_note_id': name,
                            'expected_terms': [name.capitalize()],
                        }
                    ],
                }
            ),
            encoding='utf-8',
        )
        cases.append({'case_id': name, 'document_path': f'{name}.md', 'dataset_path': f'{name}.json'})
    (tmp_path / 'negativas.json').write_text(
        json.dumps({'dataset_name': 'negativas', 'samples': [{'sample_id': 'neg-1', 'question': 'Qual a receita anual do refeitorio?', 'category': 'negativa'}]}),
        encoding='utf-8',
    )
    suite_path = tmp_path / 'suite.json'
    suite_path.write_text(
        json.dumps({'suite_name': 'ia-suite', 'cases': cases, 'negative_dataset_path': 'negativas.json'}),
        encoding='utf-8',
    )
    return suite_path


def _comparar(tmp_path: Path, suite_path: Path, nome: str, provider: FakeAnswerProvider | None = None):
    pasta = tmp_path / nome
    return compare_benchmark_suite(
        load_benchmark_suite(suite_path),
        workspace_dir=tmp_path,
        connection=init_sqlite(pasta / 'benchmark.sqlite3'),
        top_k=3,
        chunk_size=200,
        overlap=20,
        vector_store=LocalVectorStore(pasta / 'vector_store', collection_name=f'{nome}_compare'),
        embedder=FakeEmbedder(),
        answer_provider=provider,
    )


def _linha(**campos) -> BenchmarkQueryResult:
    return BenchmarkQueryResult(sample_id='s', question='q', hit_at_k=0, reciprocal_rank=0.0, latency_ms=0, **campos)


def test_limitacao_da_validacao_vira_o_mesmo_codigo_do_motivo() -> None:
    casos = {
        'echoed_context_metadata': ('Resposta: source_path: nota.md', 'O prazo e curto.'),
        'unsupported_number': ('O limite e 987654 requisicoes por minuto.', 'O limite e 10 requisicoes por minuto.'),
        'unsupported_anchor': ('O padrao adotado e o Zorbax.', 'O padrao adotado e o Kafka.'),
        'low_claim_overlap': ('alfa beta gamma delta epsilon', 'O timeout do Redis esta configurado.'),
    }
    for motivo, (resposta, contexto) in casos.items():
        validacao = validate_generated_answer('pergunta', resposta, [contexto], [])
        assert validacao.reason == motivo
        assert limitation_code(validacao.limitations) == motivo


def test_motivo_do_descarte_respeita_provider_aceite_e_abstencao() -> None:
    def resposta(**campos) -> AskResponse:
        base = {'query': 'q', 'status': 'answer', 'no_answer': False, 'answer': 'x', 'latency_ms': 1}
        return AskResponse(**{**base, **campos})

    assert generation_discard_reason(resposta(limitations=['unsupported_number: x']), has_provider=False) is None
    assert generation_discard_reason(resposta(generated=True), has_provider=True) is None
    assert generation_discard_reason(
        resposta(limitations=['Provider de resposta falhou; usando resposta extrativa. Erro: TimeoutError.']),
        has_provider=True,
    ) == 'provider_error'
    assert generation_discard_reason(
        AskResponse(
            query='q', status='no_answer', no_answer=True, answer=None,
            reason_for_no_answer='generated_generic_no_answer', latency_ms=1,
        ),
        has_provider=True,
    ) == 'generated_generic_no_answer'
    assert generation_discard_reason(
        AskResponse(query='q', status='no_answer', no_answer=True, answer=None, reason_for_no_answer='sem_trecho', latency_ms=1),
        has_provider=True,
    ) is None


def test_resumo_da_ia_conta_aceite_motivos_e_latencia_da_pergunta() -> None:
    rows = [
        _linha(answered=True, generated=True, question_latency_ms=100),
        _linha(answered=True, generated=False, discard_reason='unsupported_number', question_latency_ms=300),
        _linha(answered=False, generated=False, discard_reason='generated_generic_no_answer', question_latency_ms=200),
        _linha(answered=False, generated=False, discard_reason=None, question_latency_ms=50),
    ]

    metricas = _summarize_answer_metrics(rows, has_provider=True)

    assert (metricas.answer_count, metricas.accepted_count, metricas.accepted_rate) == (2, 1, 0.5)
    assert metricas.discard_reasons == {'generated_generic_no_answer': 1, 'unsupported_number': 1}
    assert metricas.question_p50_ms == 150.0
    assert _summarize_answer_metrics(rows, has_provider=False).accepted_rate is None


def test_compare_no_corpus_registra_provider_e_motivos_do_descarte(tmp_path: Path) -> None:
    suite_path = _suite_com_corpus(tmp_path)

    base = _comparar(tmp_path, suite_path, 'base')
    assert (base.answer_provider, base.answer_model) == ('extractive', None)
    base_ia = base.corpus.summaries['hybrid'].answer_metrics
    assert base_ia.accepted_rate is None and base_ia.discard_reasons == {}
    respondidas = base_ia.answer_count
    assert respondidas > 0  # sem perguntas respondidas não há o que a validação descartar

    falha = _comparar(tmp_path, suite_path, 'falha', FakeAnswerProvider(error=RuntimeError('timeout')))
    assert (falha.answer_provider, falha.answer_model) == ('fake', 'fake-qchat')
    falha_ia = falha.corpus.summaries['hybrid'].answer_metrics
    assert falha_ia.answer_count == respondidas
    assert falha_ia.accepted_rate == 0.0
    assert falha_ia.discard_reasons == {'provider_error': respondidas}

    # Quando a validação troca a resposta por abstenção, ela sai de `answer`: a taxa de aceite fica sem denominador.
    sentinela = _comparar(tmp_path, suite_path, 'sentinela', FakeAnswerProvider(reply=NO_ANSWER_SENTINEL))
    sentinela_ia = sentinela.corpus.summaries['hybrid'].answer_metrics
    assert sentinela_ia.answer_count == 0 and sentinela_ia.accepted_rate is None
    assert sentinela_ia.discard_reasons == {'generated_no_answer_sentinel': respondidas}


def _suite_vazia_e_settings(monkeypatch, tmp_path: Path) -> Path:
    settings = Settings(
        workspace_dir=tmp_path,
        data_dir=tmp_path / 'data',
        notes_dir=tmp_path / 'data' / 'corpus' / 'notes',
        datasets_dir=tmp_path / 'data' / 'datasets',
        results_dir=tmp_path / 'data' / 'results',
        sqlite_path=tmp_path / 'data' / 'results' / 'escolio.sqlite3',
        vector_store_dir=tmp_path / 'data' / 'results' / 'vector_store',
        embedding_model='sentence-transformer:fake-hash',
    )
    suite_path = tmp_path / 'suite.json'
    suite_path.write_text(json.dumps({'suite_name': 'cli-ia-suite', 'cases': []}), encoding='utf-8')
    monkeypatch.setattr('escolio.benchmark.cli.get_settings', lambda: settings)
    return suite_path


def test_benchmark_compare_cli_entrega_o_provider_ao_benchmark(monkeypatch, tmp_path: Path) -> None:
    suite_path = _suite_vazia_e_settings(monkeypatch, tmp_path)
    chamada: dict = {}

    def fake_compare(*args, **kwargs):
        chamada.update(kwargs)
        return SimpleNamespace(comparison_id='cmp-cli', model_dump=lambda mode='json': {'comparison_id': 'cmp-cli'})

    monkeypatch.setattr('escolio.benchmark.cli.init_sqlite', lambda path: SimpleNamespace(close=lambda: None))
    monkeypatch.setattr('escolio.benchmark.cli.LocalVectorStore', lambda *args, **kwargs: object())
    monkeypatch.setattr('escolio.benchmark.cli.get_embedder', lambda *args, **kwargs: FakeEmbedder())
    monkeypatch.setattr('escolio.benchmark.cli.compare_benchmark_suite', fake_compare)

    # Sem opções, o benchmark continua no extrativo.
    assert runner.invoke(app, ['benchmark', 'compare', '--suite', str(suite_path)]).exit_code == 0
    assert chamada['answer_provider'] is None

    result = runner.invoke(
        app,
        ['benchmark', 'compare', '--suite', str(suite_path), '--answer-provider', 'ollama', '--answer-model', 'qchat:latest'],
    )

    assert result.exit_code == 0, result.output
    provider = chamada['answer_provider']
    assert isinstance(provider, OpenAICompatibleAnswerProvider)
    assert (provider.provider_name, provider.model, provider.base_url) == ('ollama', 'qchat:latest', 'http://localhost:11434/v1')


def test_benchmark_compare_cli_recusa_modelo_sem_provider_generativo(monkeypatch, tmp_path: Path) -> None:
    suite_path = _suite_vazia_e_settings(monkeypatch, tmp_path)
    chamadas: list[dict] = []
    monkeypatch.setattr('escolio.benchmark.cli.compare_benchmark_suite', lambda *args, **kwargs: chamadas.append(kwargs))

    result = runner.invoke(app, ['benchmark', 'compare', '--suite', str(suite_path), '--answer-model', 'qchat:latest'])

    assert result.exit_code != 0
    assert chamadas == []


def _resumo(estrategia: str, ia: BenchmarkAnswerMetrics | None = None) -> BenchmarkStrategySummary:
    return BenchmarkStrategySummary(
        strategy=estrategia,
        case_count=2,
        query_count=2,
        mrr=0.942,
        recall_at_3=1.0,
        recall_at_5=1.0,
        recall_at_10=1.0,
        ndcg_at_10=1.0,
        duration_ms=1,
        avg_query_latency_ms=1.0,
        abstention={'support': 3.0, 'accuracy': 0.808, 'precision': 1.0, 'recall': 1.0, 'f1': 1.0, 'answered_positive_rate': 0.974},
        answer_metrics=ia,
    )


def _resultado(provider: str, model: str | None, *, respostas: int, aceitas: int, motivos: dict[str, int]) -> BenchmarkComparisonResult:
    taxa = aceitas / respostas if respostas and provider != 'extractive' else None
    ia = BenchmarkAnswerMetrics(
        answer_count=respostas,
        accepted_count=aceitas,
        accepted_rate=taxa,
        discard_reasons=motivos,
        question_p50_ms=120.0,
        question_p95_ms=480.0,
    )
    agora = datetime(2026, 10, 19, 12, 0, tzinfo=UTC)
    return BenchmarkComparisonResult(
        comparison_id=f'cmp-{provider}',
        suite_name='manual-validation-retrieval-suite',
        embedding_model='fake-hash',
        top_k=3,
        chunk_size=800,
        overlap=120,
        summaries={estrategia: _resumo(estrategia) for estrategia in ESTRATEGIAS},
        cases=[],
        corpus=BenchmarkCorpusResult(
            note_count=2,
            positive_count=2,
            negative_count=1,
            retrieval_depth=10,
            summaries={estrategia: _resumo(estrategia, ia) for estrategia in ESTRATEGIAS},
            queries={},
        ),
        answer_provider=provider,
        answer_model=model,
        started_at=agora,
        finished_at=agora,
        duration_ms=1,
    )


def test_report_ia_cli_monta_tabela_com_os_dois_runs(tmp_path: Path) -> None:
    extrativo = _resultado('extractive', None, respostas=0, aceitas=0, motivos={})
    generativo = _resultado('ollama', 'qchat:latest', respostas=4, aceitas=3, motivos={'unsupported_number': 1})
    (tmp_path / 'extractive.json').write_text(extrativo.model_dump_json(), encoding='utf-8')
    (tmp_path / 'qchat.json').write_text(generativo.model_dump_json(), encoding='utf-8')
    saida = tmp_path / 'relatorio' / 'ia.md'

    result = runner.invoke(
        app,
        [
            'benchmark', 'report-ia',
            '--extractive', str(tmp_path / 'extractive.json'),
            '--generativo', str(tmp_path / 'qchat.json'),
            '--saida', str(saida),
        ],
    )

    assert result.exit_code == 0, result.output
    texto = saida.read_text(encoding='utf-8')
    assert '| hybrid | Extractive | 0,974 | 0,808 | 0,942 | — | — | 120 | 480 |' in texto
    assert '| hybrid | Generativo | 0,974 | 0,808 | 0,942 | 0,750 (3/4) | unsupported_number: 1 | 120 | 480 |' in texto
    assert '## Como reproduzir' in texto
