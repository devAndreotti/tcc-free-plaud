import hashlib
import logging
import mimetypes
from pathlib import Path
from uuid import uuid4

from escolio.ingest.loaders import PDF_PARSE_FAILED, load_document
from escolio.ingest.models import IngestionResult
from escolio.ingest.validators import has_indexable_content
from escolio.providers.audio_models import AudioError

logger = logging.getLogger("escolio.ingest")
EMPTY_CONTENT = "EMPTY_CONTENT"
UNSUPPORTED_MEDIA_TYPE = "UNSUPPORTED_MEDIA_TYPE"


def _error_code_for_value_error(exc: ValueError) -> str:
    if isinstance(exc, AudioError):
        return exc.code
    text = str(exc)
    if text in {EMPTY_CONTENT, PDF_PARSE_FAILED}:
        return text
    return UNSUPPORTED_MEDIA_TYPE


def _build_ingestion_id() -> str:
    return f"ing-{uuid4().hex[:12]}"


def _build_correlation_id() -> str:
    return f"corr-{uuid4().hex[:12]}"


def _detect_media_type(path: Path) -> str | None:
    media_type, _ = mimetypes.guess_type(path.name)
    return media_type


def _build_content_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source_type_from_path(path: Path) -> str | None:
    suffix = path.suffix.lower().removeprefix(".")
    return suffix or None


def ingest_file(path: Path, correlation_id: str | None = None) -> IngestionResult:
    """Executa a ingestão textual mínima com validação, rastreabilidade e logs."""
    source_path = Path(path)
    ingestion_id = _build_ingestion_id()
    resolved_correlation_id = correlation_id or _build_correlation_id()

    logger.info(
        "ingestion.started correlation_id=%s ingestion_id=%s source_path=%s",
        resolved_correlation_id,
        ingestion_id,
        source_path,
    )

    try:
        size_bytes = source_path.stat().st_size
        content_sha256 = _build_content_hash(source_path)
        detected_media_type = _detect_media_type(source_path)
        document = load_document(source_path)

        if not has_indexable_content(document):
            raise ValueError(EMPTY_CONTENT)

        result = IngestionResult(
            ingestion_id=ingestion_id,
            correlation_id=resolved_correlation_id,
            source_path=document.source_path,
            source_type=document.source_type,
            detected_media_type=detected_media_type,
            status="success",
            size_bytes=size_bytes,
            content_sha256=content_sha256,
            raw_text=document.raw_text,
            message="Document ingested successfully.",
        )

        logger.info(
            "ingestion.completed correlation_id=%s ingestion_id=%s source_path=%s source_type=%s",
            resolved_correlation_id,
            ingestion_id,
            source_path,
            document.source_type,
        )
        return result
    except FileNotFoundError:
        logger.error(
            "ingestion.failed correlation_id=%s ingestion_id=%s source_path=%s error_code=INPUT_NOT_FOUND",
            resolved_correlation_id,
            ingestion_id,
            source_path,
        )
        return IngestionResult(
            ingestion_id=ingestion_id,
            correlation_id=resolved_correlation_id,
            source_path=source_path,
            source_type=_source_type_from_path(source_path),
            status="failed",
            error_code="INPUT_NOT_FOUND",
            message="Source file not found.",
        )
    except ValueError as exc:
        error_code = _error_code_for_value_error(exc)
        logger.error(
            "ingestion.failed correlation_id=%s ingestion_id=%s source_path=%s error_code=%s",
            resolved_correlation_id,
            ingestion_id,
            source_path,
            error_code,
        )
        return IngestionResult(
            ingestion_id=ingestion_id,
            correlation_id=resolved_correlation_id,
            source_path=source_path,
            source_type=_source_type_from_path(source_path),
            detected_media_type=_detect_media_type(source_path),
            status="failed",
            error_code=error_code,
            message=str(exc),
        )
