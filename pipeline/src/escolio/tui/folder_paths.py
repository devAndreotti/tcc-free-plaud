from pathlib import Path

from escolio.corpus.models import CorpusIndexBatchResult


def _resolve_folder_path(folder_path: Path | str) -> Path:
    raw_path = str(folder_path).strip()
    if not raw_path:
        raise ValueError("Informe uma pasta para indexar.")

    target = Path(raw_path).expanduser()
    if not target.exists():
        raise FileNotFoundError(f"Pasta nao encontrada: {target}")
    if not target.is_dir():
        raise ValueError(f"Path precisa ser pasta: {target}")
    return target



def _failed_batch(path: Path, message: str) -> CorpusIndexBatchResult:
    _ = message
    return CorpusIndexBatchResult(
        source_path=str(path),
        recursive=True,
        status="failed",
        total_found=0,
        indexed_count=0,
        failed_count=0,
        skipped_count=0,
        results=[],
        skipped=[],
    )


