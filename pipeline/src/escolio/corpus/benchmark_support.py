import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

from escolio.app.config import Settings
from escolio.corpus.models import CorpusIndexBatchResult
from escolio.providers.embed import Embedder

# Dependencias injetadas pela fachada service (index_fn, get_embedder_fn), resolvidas em tempo de chamada:
# assim monkeypatch em escolio.corpus.service.get_embedder continua valendo e nao ha ciclo de import.
IndexFn = Callable[..., CorpusIndexBatchResult]
EmbedderFactory = Callable[..., Embedder]


class CountingEmbedder:
    def __init__(self, embedder: Embedder) -> None:
        self._embedder = embedder
        self.model_name = embedder.model_name
        self.calls = 0

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls += 1
        return self._embedder.embed(texts)


def build_benchmark_settings(base: Settings, workspace_dir: Path) -> Settings:
    data_dir = workspace_dir / 'data'
    return Settings(
        environment=base.environment,
        workspace_dir=workspace_dir,
        data_dir=data_dir,
        notes_dir=data_dir / 'corpus' / 'notes',
        datasets_dir=data_dir / 'datasets',
        results_dir=data_dir / 'results',
        sqlite_path=data_dir / 'results' / 'escolio.sqlite3',
        vector_store_dir=data_dir / 'results' / 'vector_store',
        vector_collection_name=base.vector_collection_name,
        embedding_model=base.embedding_model,
        embedding_device=base.embedding_device,
        default_chunk_size=base.default_chunk_size,
        default_chunk_overlap=base.default_chunk_overlap,
        retrieval_top_k=base.retrieval_top_k,
        corpus_commit_mode=base.corpus_commit_mode,
        corpus_micro_batch_chunks=base.corpus_micro_batch_chunks,
        corpus_micro_batch_files=base.corpus_micro_batch_files,
        corpus_atomic_max_files=base.corpus_atomic_max_files,
        corpus_atomic_max_chunks=base.corpus_atomic_max_chunks,
        corpus_embedding_batch_size=base.corpus_embedding_batch_size,
        corpus_upsert_batch_size=base.corpus_upsert_batch_size,
        corpus_index_workers=base.corpus_index_workers,
    )


def write_index_benchmark_fixture(root: Path, files: int) -> int:
    root.mkdir(parents=True, exist_ok=True)
    for index in range(files):
        suffix = '.txt' if index % 5 == 0 else '.md'
        path = root / f'documento-{index:03d}{suffix}'
        repeated = 12 if index % 4 == 0 else 3
        body = (
            f'# Documento {index:03d}\n\n'
            f'Arquivo sintetico {index:03d} para benchmark de indexacao local-first. '
            'RabbitMQ, runbook SRE e pipeline Bronze Silver Gold aparecem como termos controlados. '
        )
        path.write_text(body * repeated, encoding='utf-8')

    (root / 'ignorado.png').write_text('fora do corpus', encoding='utf-8')
    (root / 'ignorado.docx').write_text('fora do corpus', encoding='utf-8')
    (root / 'ignorado.canvas').write_text('fora do corpus', encoding='utf-8')
    return 3


def rate(amount: int, elapsed_ms: int) -> float:
    if amount <= 0 or elapsed_ms <= 0:
        return 0.0
    return round(amount / (elapsed_ms / 1000), 3)


def git_commit_for_path(path: Path) -> str | None:
    try:
        completed = subprocess.run(
            ['git', 'rev-parse', 'HEAD'],
            cwd=path,
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception:
        return None
    commit = completed.stdout.strip()
    return commit or None


def torch_environment() -> dict[str, object]:
    payload: dict[str, object] = {
        'python': sys.version.split()[0],
        'executable': sys.executable,
    }
    try:
        import torch
    except Exception as exc:
        payload.update(
            {
                'torch_version': None,
                'cuda_available': False,
                'gpu_name': None,
                'torch_error': f'{type(exc).__name__}: {exc}',
            }
        )
        return payload

    cuda_available = bool(torch.cuda.is_available())
    payload.update(
        {
            'torch_version': getattr(torch, '__version__', None),
            'torch_cuda_version': getattr(torch.version, 'cuda', None),
            'cuda_available': cuda_available,
            'gpu_name': torch.cuda.get_device_name(0) if cuda_available else None,
        }
    )
    if cuda_available:
        try:
            payload['peak_vram_mb'] = int(torch.cuda.max_memory_allocated(0) / (1024 * 1024))
        except Exception:
            payload['peak_vram_mb'] = None
    return payload


def percentile(values: list[int], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = round((len(ordered) - 1) * percentile)
    return float(ordered[index])
