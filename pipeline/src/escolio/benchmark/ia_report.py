"""Relatório do TCC: a IA local (provider generativo) contra o extractive, a partir dos JSONs do compare."""

from escolio.benchmark.runners import (
    BenchmarkComparisonResult,
    BenchmarkStrategySummary,
)

STRATEGIAS = ('lexical', 'vector', 'hybrid')
CABECALHO_TABELA = (
    '| Estratégia | Modo | Positivas respondidas | Accuracy | MRR | Aceitas pela validação | Motivos de descarte | p50 (ms) | p95 (ms) |',
    '|---|---|---:|---:|---:|---:|---|---:|---:|',
)
COMO_REPRODUZIR = (
    '## Como reproduzir',
    '',
    'A partir de `pipeline/`, com o Python do venv:',
    '',
    '```bash',
    'python -m escolio benchmark compare --suite ../data/datasets/manual_validation/suite.json > ../data/results/bench_extractive.json',
    'python -m escolio benchmark compare --suite ../data/datasets/manual_validation/suite.json --answer-provider ollama --answer-model qchat:latest > ../data/results/bench_qchat.json',
    'python -m escolio benchmark report-ia --extractive ../data/results/bench_extractive.json --generativo ../data/results/bench_qchat.json --saida relatorio.md',
    '```',
)


def _decimal(valor: float | None) -> str:
    return '—' if valor is None else f'{valor:.3f}'.replace('.', ',')


def linha_tabela(modo: str, resumo: BenchmarkStrategySummary) -> str:
    """Uma linha da tabela por estratégia; reutilizada pelo relatório de modelos (model_compare)."""
    abstencao = resumo.abstention or {}
    ia = resumo.answer_metrics
    aceitas = motivos = p50 = p95 = '—'
    if ia is not None:
        if ia.accepted_rate is not None:
            aceitas = f'{_decimal(ia.accepted_rate)} ({ia.accepted_count}/{ia.answer_count})'
        motivos = ', '.join(f'{codigo}: {quantidade}' for codigo, quantidade in ia.discard_reasons.items()) or '—'
        p50, p95 = f'{ia.question_p50_ms:.0f}', f'{ia.question_p95_ms:.0f}'
    return (
        f'| {resumo.strategy} | {modo} | {_decimal(abstencao.get("answered_positive_rate"))} '
        f'| {_decimal(abstencao.get("accuracy"))} | {_decimal(resumo.mrr)} | {aceitas} | {motivos} | {p50} | {p95} |'
    )


def build_ia_report(extractive: BenchmarkComparisonResult, generativo: BenchmarkComparisonResult) -> str:
    """Markdown em português com a tabela por estratégia; só números, sem conclusão."""
    if extractive.corpus is None or generativo.corpus is None:
        raise ValueError('Os dois JSONs precisam da passada no corpus; gere-os com `benchmark compare`.')
    corpus = generativo.corpus
    linhas = [
        '# IA local (qchat) contra o extractive',
        '',
        f'Suíte `{generativo.suite_name}`, medida em {generativo.started_at:%Y-%m-%d %H:%M} (UTC).',
        (
            f'Corpus: {corpus.note_count} notas, {corpus.positive_count} perguntas positivas e '
            f'{corpus.negative_count} negativas, profundidade {corpus.retrieval_depth}.'
        ),
        '',
        '| Run | Provider | Modelo | Comparação |',
        '|---|---|---|---|',
        f'| Extractive | {extractive.answer_provider} | — | `{extractive.comparison_id}` |',
        f'| Generativo | {generativo.answer_provider} | {generativo.answer_model or "—"} | `{generativo.comparison_id}` |',
        '',
        '## Resultados por estratégia',
        '',
        *CABECALHO_TABELA,
    ]
    for estrategia in STRATEGIAS:
        linhas.append(linha_tabela('Extractive', extractive.corpus.summaries[estrategia]))
        linhas.append(linha_tabela('Generativo', corpus.summaries[estrategia]))
    linhas += [
        '',
        (
            'Positivas respondidas, accuracy e MRR vêm da passada no corpus (todas as notas, sem filtro por nota, '
            'com as negativas). Aceitas pela validação = respostas geradas aceitas / respostas `answer`; os motivos '
            'incluem as negativas que a validação trocou por abstenção. p50 e p95 medem a pergunta inteira '
            '(recuperação e resposta).'
        ),
        '',
        *COMO_REPRODUZIR,
    ]
    return '\n'.join(linhas) + '\n'
