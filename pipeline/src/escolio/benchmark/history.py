"""O que a tela de Benchmark mostra sem rodar nada: prévia da suite e rodadas já gravadas."""

import json
import re
from pathlib import Path

from escolio.app.config import Settings, get_settings
from escolio.benchmark.datasets import load_benchmark_dataset, load_benchmark_suite

RUN_ID = re.compile(r'^cmp-[0-9a-f]{12}$')
PREVIEW_QUESTION_LIMIT = 500
# (caminho, mtime) -> linha. Cada JSON tem 1,5 MB: reler todos a cada visita à tela custaria segundos.
_row_cache: dict[tuple[str, int], dict] = {}


def _suite_file(suite_path: str | Path, settings: Settings) -> Path:
    path = Path(suite_path).expanduser()
    return path if path.is_absolute() else settings.workspace_dir / path


def preview_benchmark_suite(suite_path: str | Path, *, settings: Settings | None = None) -> dict:
    """Lê a suite sem indexar nada: quantas notas e perguntas, e as perguntas em si."""
    resolved = settings or get_settings()
    suite = load_benchmark_suite(_suite_file(suite_path, resolved))
    questions: list[dict] = []
    positive_count = 0
    for case in suite.cases:
        dataset = load_benchmark_dataset(resolved.workspace_dir / case.dataset_path)
        positive_count += len(dataset.samples)
        note = Path(case.document_path).stem
        questions.extend(
            {'question': sample.question, 'note': note, 'expected_ref': sample.expected_ref, 'negative': False}
            for sample in dataset.samples
        )
    negative_count = 0
    if suite.negative_dataset_path:
        negatives = load_benchmark_dataset(resolved.workspace_dir / suite.negative_dataset_path).samples
        negative_count = len(negatives)
        questions.extend(
            {'question': sample.question, 'note': None, 'expected_ref': None, 'negative': True}
            for sample in negatives
        )
    return {
        'suite_name': suite.suite_name,
        'note_count': len(suite.cases),
        'positive_count': positive_count,
        'negative_count': negative_count,
        'questions': questions[:PREVIEW_QUESTION_LIMIT],
    }


def negative_subtypes(suite_path: str | Path, *, settings: Settings | None = None) -> dict[str, str]:
    """Tipo de cada pergunta sem resposta, quando a suite marca (`subtipo` no dataset). Só o lote cego marca."""
    resolved = settings or get_settings()
    suite = load_benchmark_suite(_suite_file(suite_path, resolved))
    if not suite.negative_dataset_path:
        return {}
    payload = json.loads((resolved.workspace_dir / suite.negative_dataset_path).read_text(encoding='utf-8'))
    samples = payload.get('samples', []) if isinstance(payload, dict) else payload
    return {sample['sample_id']: sample['subtipo'] for sample in samples if sample.get('subtipo')}


def _subtypes_by_suite_name(name: object, settings: Settings) -> dict[str, str]:
    # Rodada gravada antes de o JSON guardar os tipos: acha a suite pelo nome.
    for suite_file in sorted(settings.datasets_dir.glob('*/suite.json')):
        try:
            if json.loads(suite_file.read_text(encoding='utf-8')).get('suite_name') == name:
                return negative_subtypes(suite_file, settings=settings)
        except (OSError, ValueError, KeyError):
            continue
    return {}


def _run_row(path: Path, data: dict) -> dict:
    corpus = data.get('corpus') or {}
    summary = (corpus.get('summaries') or data.get('summaries') or {}).get('hybrid') or {}
    abstention = summary.get('abstention') or {}
    provider = data.get('answer_provider') or 'extractive'
    return {
        'comparison_id': data.get('comparison_id') or path.stem,
        'suite_name': data.get('suite_name'),
        'started_at': data.get('started_at'),
        'duration_ms': data.get('duration_ms'),
        'answer_provider': provider,
        'answer_model': data.get('answer_model') if provider != 'extractive' else None,
        'positive_count': corpus.get('positive_count'),
        'negative_count': corpus.get('negative_count'),
        'mrr': summary.get('mrr'),
        'recall_at_3': summary.get('recall_at_3'),
        'answered_positive_rate': abstention.get('answered_positive_rate'),
        'abstention_recall': abstention.get('recall'),
        'accuracy': abstention.get('accuracy'),
    }


def list_benchmark_runs(*, settings: Settings | None = None, limit: int = 30) -> list[dict]:
    """Rodadas gravadas em results_dir, da mais recente para a mais antiga. Arquivo ilegível fica de fora."""
    resolved = settings or get_settings()
    stamped: list[tuple[int, Path]] = []
    for path in resolved.results_dir.glob('cmp-*.json'):
        if RUN_ID.match(path.stem):
            stamped.append((path.stat().st_mtime_ns, path))
    stamped.sort(key=lambda item: item[0], reverse=True)
    rows: list[dict] = []
    for mtime, path in stamped[:limit]:
        key = (str(path), mtime)
        row = _row_cache.get(key)
        if row is None:
            try:
                row = _run_row(path, json.loads(path.read_text(encoding='utf-8')))
            except (OSError, ValueError, AttributeError):
                continue
            _row_cache[key] = row
        rows.append(row)
    return rows


def load_benchmark_run(comparison_id: str, *, settings: Settings | None = None) -> dict:
    """Devolve uma rodada gravada no mesmo formato da que acabou de rodar."""
    if not RUN_ID.match(comparison_id):  # vem da tela: nunca vira caminho sem passar por aqui
        raise ValueError(f'Rodada inválida: {comparison_id}')
    resolved = settings or get_settings()
    json_path = resolved.results_dir / f'{comparison_id}.json'
    if not json_path.is_file():
        raise ValueError(f'Rodada não encontrada: {comparison_id}')
    payload = json.loads(json_path.read_text(encoding='utf-8'))
    csv_path = json_path.with_suffix('.csv')
    if 'negative_subtypes' not in payload:
        payload['negative_subtypes'] = _subtypes_by_suite_name(payload.get('suite_name'), resolved)
    payload.update({
        'ok': True,
        'json_report_path': str(json_path),
        'csv_report_path': str(csv_path) if csv_path.is_file() else '',
    })
    return payload
