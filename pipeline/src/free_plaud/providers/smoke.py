import shutil
import tempfile
from pathlib import Path
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel

from free_plaud.app.config import Settings, get_settings
from free_plaud.corpus.ask import RetrievalStrategy, answer_corpus_with_citations
from free_plaud.corpus.service import index_corpus_path
from free_plaud.providers.answer import AnswerProvider, AnswerProviderTestResult, get_answer_provider, test_answer_provider
from free_plaud.providers.embed import get_embedder
from free_plaud.retrieval.models import AskResponse
from free_plaud.storage.sqlite import init_sqlite
from free_plaud.storage.vector import LocalVectorStore

SMOKE_KNOWN_QUESTION = 'O que e Estrutura Disco D?'
SMOKE_MISSING_QUESTION = 'Existe algo sobre quantum banana inexistente?'


class ProviderSmokeAskResult(BaseModel):
    question: str
    status: Literal['answer', 'no_answer']
    answer: str | None = None
    reason_for_no_answer: str | None = None
    latency_ms: int
    citations_count: int
    used_sources_count: int


class ProviderSmokeLocalResult(BaseModel):
    status: Literal['ok', 'error']
    strategy: RetrievalStrategy
    top_k: int
    provider_test: AnswerProviderTestResult
    known_question: ProviderSmokeAskResult
    missing_question: ProviderSmokeAskResult
    workspace_dir: str | None = None
    error: str | None = None


def _write_smoke_corpus(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / 'estrutura-disco-c.md').write_text(
        '# Estrutura Disco C\n\n'
        'Estrutura Disco C descreve a organizacao do disco C para arquivos do sistema operacional.\n',
        encoding='utf-8',
    )
    (root / 'estrutura-disco-d.md').write_text(
        '# Estrutura Disco D\n\n'
        'Estrutura Disco D descreve a organizacao do disco D para arquivos de trabalho e repositorios.\n',
        encoding='utf-8',
    )


def _smoke_settings(base: Settings, workspace_dir: Path) -> Settings:
    data_dir = workspace_dir / 'data'
    results_dir = data_dir / 'results'
    return Settings(
        **{
            **base.model_dump(),
            'workspace_dir': workspace_dir,
            'data_dir': data_dir,
            'notes_dir': data_dir / 'corpus' / 'notes',
            'datasets_dir': data_dir / 'datasets',
            'results_dir': results_dir,
            'sqlite_path': results_dir / 'free_plaud_smoke.sqlite3',
            'vector_store_dir': results_dir / 'vector_store',
            'vector_collection_name': f'provider_smoke_{uuid4().hex}',
            'answer_api_key': base.answer_api_key,
        }
    )


def _summarize_ask_response(response: AskResponse) -> ProviderSmokeAskResult:
    return ProviderSmokeAskResult(
        question=response.query,
        status=response.status,
        answer=response.answer,
        reason_for_no_answer=response.reason_for_no_answer,
        latency_ms=response.latency_ms,
        citations_count=len(response.citations),
        used_sources_count=len(response.used_sources),
    )


def _resolve_answer_provider(settings: Settings, injected_provider: AnswerProvider | None) -> AnswerProvider | None:
    if injected_provider is not None:
        return injected_provider
    return get_answer_provider(
        settings.answer_provider,
        model=settings.answer_model,
        base_url=settings.answer_base_url,
        api_key=settings.answer_api_key,
        temperature=settings.answer_temperature,
        max_tokens=settings.answer_max_tokens,
        timeout_seconds=settings.answer_timeout_seconds,
    )


def run_provider_smoke_local(
    *,
    settings: Settings | None = None,
    strategy: RetrievalStrategy = 'lexical',
    top_k: int = 4,
    keep_workspace: bool = False,
    answer_provider: AnswerProvider | None = None,
    provider_test_result: AnswerProviderTestResult | None = None,
) -> ProviderSmokeLocalResult:
    """Roda smoke manual reproduzivel em corpus temporario, sem tocar no vault real."""
    base_settings = settings or get_settings()
    workspace_dir = Path(tempfile.mkdtemp(prefix='free-plaud-smoke-'))
    smoke_settings = _smoke_settings(base_settings, workspace_dir)

    try:
        corpus_root = workspace_dir / 'corpus'
        _write_smoke_corpus(corpus_root)
        connection = init_sqlite(smoke_settings.sqlite_path)
        vector_store = None
        embedder = None
        if strategy in {'vector', 'hybrid'}:
            embedder = get_embedder(smoke_settings.embedding_model, device=smoke_settings.embedding_device)
            vector_store = LocalVectorStore(
                smoke_settings.vector_store_dir,
                collection_name=smoke_settings.vector_collection_name,
            )

        index_corpus_path(
            corpus_root,
            settings=smoke_settings,
            connection=connection,
            vector_store=vector_store,
            embedder=embedder,
            recursive=True,
        )

        provider_test = provider_test_result or test_answer_provider(smoke_settings)
        provider = _resolve_answer_provider(smoke_settings, answer_provider)
        known_response = answer_corpus_with_citations(
            SMOKE_KNOWN_QUESTION,
            connection=connection,
            vector_store=vector_store,
            embedder=embedder,
            strategy=strategy,
            top_k=top_k,
            answer_provider=provider,
            include_debug=True,
        )
        missing_response = answer_corpus_with_citations(
            SMOKE_MISSING_QUESTION,
            connection=connection,
            vector_store=vector_store,
            embedder=embedder,
            strategy=strategy,
            top_k=top_k,
            answer_provider=provider,
            include_debug=True,
        )
        ok = provider_test.status in {'ok', 'not_applicable'} and known_response.status == 'answer' and missing_response.status == 'no_answer'
        return ProviderSmokeLocalResult(
            status='ok' if ok else 'error',
            strategy=strategy,
            top_k=top_k,
            provider_test=provider_test,
            known_question=_summarize_ask_response(known_response),
            missing_question=_summarize_ask_response(missing_response),
            workspace_dir=str(workspace_dir) if keep_workspace else None,
            error=None if ok else 'Smoke local nao atendeu todos os criterios esperados.',
        )
    except Exception as exc:  # noqa: BLE001 - comando de smoke deve retornar erro estruturado.
        fallback_provider_test = provider_test_result or AnswerProviderTestResult(
            provider=base_settings.answer_provider,
            model=base_settings.answer_model,
            base_url=base_settings.answer_base_url,
            status='error',
            latency_ms=0,
            error='Smoke falhou antes do teste de provider.',
        )
        empty_result = ProviderSmokeAskResult(
            question='',
            status='no_answer',
            latency_ms=0,
            citations_count=0,
            used_sources_count=0,
            reason_for_no_answer='smoke_failed',
        )
        return ProviderSmokeLocalResult(
            status='error',
            strategy=strategy,
            top_k=top_k,
            provider_test=fallback_provider_test,
            known_question=empty_result,
            missing_question=empty_result,
            workspace_dir=str(workspace_dir) if keep_workspace else None,
            error=str(exc),
        )
    finally:
        if not keep_workspace:
            shutil.rmtree(workspace_dir, ignore_errors=True)
